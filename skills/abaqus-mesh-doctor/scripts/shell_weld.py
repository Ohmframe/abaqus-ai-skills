# -*- coding: utf-8 -*-
"""
shell_weld.py - turn a STEP shell model whose panels only TOUCH (spars, ribs, stiffeners, skins
that meet without sharing edges -> "free edges", an open structure, unmatched meshes) into one
welded, structured S4R mesh.

    abaqus cae noGUI=shell_weld.py -- step:model.step out:model_welded.cae seed:0.05 \
        [contacttol:0.001] [mergetol:1e-4] [iters:4] [stitch:0.001]

All lengths in the STEP file's units (scaleFromFile=OFF).

Workflow (each stage is written to <out>_report.txt with counts, so you can see where it stops):
  1. Import the STEP as ONE shell part, stitching edges within 'stitch'.  checkGeometry.
  2. Contact lines: every free edge of one panel that lies within 'contacttol' of another face
     is imprinted onto that face (PartitionFaceByShortestPath, fallback PartitionFaceByProjectingEdges).
     Two passes, because the first pass exposes new lines.
  3. Mesh STRUCTURED quads (S4R, S3 fallback). For every imprinted joint the coincident edges
     on both sides get the same seed number; iterate until every joint matches node-for-node.
  4. PartFromMesh + mergeNodes(tolerance=mergetol): this is what actually welds the panels.
     Reports free element edges and 3-shell junctions before and after.
  5. Whatever still has free element edges inside the structure is collected in node set
     FREE_EDGE_NODES on the mesh part: close those with a Tie, or fix the geometry.

Materials, sections, steps, loads are NOT created: this is geometry/mesh repair only.
Prove the result with scratch_static_check.py (a throw-away linear solve on a copy).

Python 2.7 and 3.  OhmFrame - https://ohmframe.com - MIT licence.
"""
from __future__ import print_function

import math
import os
import sys

from abaqus import *
from abaqusConstants import *
from caeModules import *
import part
import mesh
try:
    import builtins as _bi
except ImportError:
    import __builtin__ as _bi
sum, min, max, round, abs = _bi.sum, _bi.min, _bi.max, _bi.round, _bi.abs


def arg(key, default=None, cast=str):
    for a in sys.argv:
        if a.startswith(key + ':') or a.startswith(key + '='):
            return cast(a[len(key) + 1:])
    return default


STEPFILE = arg('step')
if not STEPFILE:
    raise SystemExit(__doc__)
OUT = arg('out', os.path.splitext(STEPFILE)[0] + '_welded.cae')
SEED = arg('seed', None, float)
CONTACT_TOL = arg('contacttol', 1.0e-3, float)
MERGE_TOL = arg('mergetol', 1.0e-4, float)
ITERS = arg('iters', 4, int)
STITCH = arg('stitch', 1.0e-3, float)

_rep = open(os.path.splitext(OUT)[0] + '_report.txt', 'w')


def note(s):
    _rep.write(str(s) + '\n')
    _rep.flush()
    sys.__stdout__.write(str(s) + '\n')
    sys.__stdout__.flush()


def dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def freestat(p):
    n, L = 0, 0.0
    for e in p.edges:
        if len(e.getFaces()) == 1:
            n += 1
            try:
                L += e.getSize(printResults=False)
            except Exception:
                pass
    return n, L


# ----------------------------------------------------------------------------- 1. import
mo = mdb.models['Model-1']
stp = mdb.openStep(STEPFILE, scaleFromFile=OFF)
pt = mo.PartFromGeometryFile(name='GEOM', geometryFile=stp, combine=True, dimensionality=THREE_D,
                             type=DEFORMABLE_BODY, convertToAnalytical=1, stitchTolerance=STITCH,
                             stitchEdges=1, scale=1.0)
bb = pt.faces.getBoundingBox()
diag = dist(bb['low'], bb['high'])
if SEED is None:
    SEED = diag / 60.0
n0, l0 = freestat(pt)
note('1. IMPORT %s' % STEPFILE)
note('   faces %d  edges %d  bbox %s -> %s  (diag %.4g)' % (len(pt.faces), len(pt.edges),
                                                          bb['low'], bb['high'], diag))
note('   free geometry edges: %d (total length %.4g)' % (n0, l0))
before = set(pt.sets.keys())
pt.checkGeometry(detailed=ON)
probs = [s for s in pt.sets.keys() if s not in before]
note('   checkGeometry: %s' % (probs or 'clean'))
for s in probs:
    del pt.sets[s]


# ----------------------------------------------------------------------------- 2. imprint
def findcontacts(p):
    out = []
    faces = list(p.faces)
    for e in p.edges:
        fs = e.getFaces()
        if len(fs) != 1:
            continue
        p0 = e.pointOn[0]
        others = [f for f in faces if f.index != fs[0]]
        if not others:
            continue
        try:
            r = part.FaceArray(others).getClosest(coordinates=(p0,), searchTolerance=10 * CONTACT_TOL)
        except Exception:
            continue
        if 0 not in r or dist(p0, r[0][1]) > CONTACT_TOL:
            continue
        vs = e.getVertices()
        if len(vs) < 2:
            continue
        out.append(dict(a=tuple(p.vertices[vs[0]].pointOn[0]), b=tuple(p.vertices[vs[1]].pointOn[0]),
                        p=tuple(p0), L=e.getSize(printResults=False), target=r[0][0].index))
    return out


def okey(o):
    ka = tuple(round(v, 6) for v in o['a'])
    kb = tuple(round(v, 6) for v in o['b'])
    return (ka, kb) if ka < kb else (kb, ka)


note('2. IMPRINT CONTACT LINES (free edge of one panel lying on another face)')
seen, allops = {}, []
for ip in range(2):
    fresh = [o for o in findcontacts(pt) if okey(o) not in seen]
    note('   pass %d: %d new contact lines (%.4g length)' % (ip + 1, len(fresh), sum(o['L'] for o in fresh)))
    if not fresh:
        break
    ok = bad = 0
    for o in fresh:
        seen[okey(o)] = 1
        try:
            tgt = pt.faces.getClosest(coordinates=(o['p'],))[0][0]   # face index may change after a cut
        except Exception:
            tgt = None
        done = False
        for attempt in (1, 2):
            try:
                if attempt == 1:
                    pt.PartitionFaceByShortestPath(faces=pt.faces[tgt.index:tgt.index + 1],
                                                   point1=o['a'], point2=o['b'])
                else:
                    pt.PartitionFaceByProjectingEdges(faces=pt.faces[tgt.index:tgt.index + 1],
                                                      edges=(pt.edges.findAt(o['p']),), extendEdges=True)
                done = True
                break
            except Exception:
                continue
        if done:
            ok += 1
            allops.append(o)
        else:
            bad += 1
    note('           imprinted %d, failed %d' % (ok, bad))
n1, l1 = freestat(pt)
note('   after imprint: faces %d  edges %d  free geometry edges %d (%.4g)' % (len(pt.faces), len(pt.edges), n1, l1))

# ----------------------------------------------------------------------------- 3. structured mesh with matched seeds
pt.setMeshControls(regions=pt.faces, elemShape=QUAD, technique=STRUCTURED)
pt.setElementType(regions=(pt.faces,), elemTypes=(mesh.ElemType(elemCode=S4R, elemLibrary=STANDARD),
                                                   mesh.ElemType(elemCode=S3, elemLibrary=STANDARD)))
alle = []
for e in pt.edges:
    vs = e.getVertices()
    if len(vs) >= 2:
        alle.append((e, pt.vertices[vs[0]].pointOn[0], pt.vertices[vs[1]].pointOn[0]))
groups = []
for o in allops:
    grp = [e for e, p1, p2 in alle
           if min(dist(p1, o['a']), dist(p2, o['a'])) < 1e-6 * max(1.0, diag)
           and min(dist(p1, o['b']), dist(p2, o['b'])) < 1e-6 * max(1.0, diag)]
    if len(grp) >= 2:
        groups.append(grp)
note('3. MESH  seed %.4g, structured quads, %d coincident edge groups to match' % (SEED, len(groups)))
forced = {}
for it in range(ITERS):
    pt.seedPart(size=SEED, deviationFactor=0.1, minSizeFactor=0.1)
    for gi, nn in forced.items():
        try:
            pt.seedEdgeByNumber(edges=part.EdgeArray(groups[gi]), number=nn, constraint=FIXED)
        except Exception:
            pass
    try:
        pt.generateMesh()
    except Exception:
        pass
    if len(pt.elements) == 0:
        note('   iter %d: structured mesher could not honour %d forced joints; plain seeding' % (it, len(forced)))
        pt.deleteSeeds(regions=pt.edges)
        pt.seedPart(size=SEED, deviationFactor=0.1, minSizeFactor=0.1)
        pt.generateMesh()
        break
    mism = 0
    for gi, grp in enumerate(groups):
        try:
            cnt = [len(e.getNodes()) for e in grp]
        except Exception:
            continue
        if len(set(cnt)) > 1:
            mism += 1
            forced[gi] = max(cnt) - 1
    note('   iter %d: nodes %d  elements %d  joints with mismatched meshes %d' % (it, len(pt.nodes), len(pt.elements), mism))
    if mism == 0:
        break
q = pt.verifyMeshQuality(criterion=ANALYSIS_CHECKS)
tri = sum(1 for el in pt.elements if len(el.connectivity) == 3)
note('   triangles %d (%.2f %%)  analysis checks: errors %d warnings %d' % (
    tri, 100.0 * tri / max(1, len(pt.elements)), len(q['failedElements']), len(q['warningElements'])))


# ----------------------------------------------------------------------------- 4. weld by node merge
def edge_use(p):
    d = {}
    for el in p.elements:
        c = el.connectivity
        n = 4 if len(c) in (4, 8, 9) else 3
        for i in range(n):
            a, b = c[i], c[(i + 1) % n]
            k = (min(a, b), max(a, b))
            d[k] = d.get(k, 0) + 1
    return d


fe = pt.PartFromMesh(name='FE', copySets=True)
d0 = edge_use(fe)
f0, j0 = sum(1 for v in d0.values() if v == 1), sum(1 for v in d0.values() if v > 2)
nb = len(fe.nodes)
fe.mergeNodes(nodes=fe.nodes, tolerance=MERGE_TOL, removeDuplicateElements=OFF)
d1 = edge_use(fe)
f1, j1 = sum(1 for v in d1.values() if v == 1), sum(1 for v in d1.values() if v > 2)
note('4. MERGE NODES tol %.3g: merged %d nodes' % (MERGE_TOL, nb - len(fe.nodes)))
note('   free element edges %d -> %d   3+-shell junctions %d -> %d' % (f0, f1, j0, j1))

# ----------------------------------------------------------------------------- 5. leftovers
free_nodes = set()
for (a, b), v in d1.items():
    if v == 1:
        free_nodes.update((a, b))
if free_nodes:
    labels = sorted(free_nodes)
    fe.Set(name='FREE_EDGE_NODES', nodes=fe.nodes.sequenceFromLabels(labels))
note('5. FREE_EDGE_NODES: %d nodes on free element edges. The outer boundary of an open structure '
     'is legitimately free; anything INSIDE the structure is an unwelded joint -> Tie it or fix it.' % len(free_nodes))
a = mo.rootAssembly
a.DatumCsysByDefault(CARTESIAN)
a.Instance(name='FE-1', part=fe, dependent=ON)
mdb.saveAs(pathName=OUT)
note('saved %s (parts GEOM = repaired geometry, FE = welded mesh)' % OUT)
_rep.close()
