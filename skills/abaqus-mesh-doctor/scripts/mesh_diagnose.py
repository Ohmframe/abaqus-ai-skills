# -*- coding: utf-8 -*-
"""
mesh_diagnose.py - read-only mesh and geometry health report for every part of a .cae.

    abaqus cae noGUI=mesh_diagnose.py -- model.cae [model:NAME] [part:NAME] [export]
    (GUI: open the .cae, then File > Run Script > mesh_diagnose.py; the open database is used)

Never saves the .cae. Temporary sets are deleted again. Writes next to the .cae:
  mesh_report.txt / mesh_report.json   per part:
     geometry   cells/faces/edges, free (one-face) geometry edges, checkGeometry problems,
                shortest edges (slivers from fillets and partition intersections)
     controls   element shape / technique / algorithm per cell (which cells are not hex/structured)
     quality    Abaqus Analysis Checks (errors, warnings) + Verify-Mesh shape metrics at
                the dialog defaults (angle <10 / >160, aspect >10, shape factor, geom deviation)
     bad cells  bad elements grouped by the geometry cell they belong to, with the cell's edges,
                seeds and lengths -> tells you WHERE to partition or reseed
     shells     element-edge sharing histogram (1 = free edge, 2 = normal, 3+ = T-junction) and
                the free-edge length of the mesh -> unconnected panels
  <model>_<part>.sat / .stp    geometry export incl. partitions (only with 'export')

Runs under Abaqus Python 2.7 and 3.  OhmFrame - https://ohmframe.com - MIT licence.
"""
from __future__ import print_function

import json
import math
import os
import sys

from abaqus import *
from abaqusConstants import *
try:
    import builtins as _bi
except ImportError:
    import __builtin__ as _bi
sum, min, max, round, abs = _bi.sum, _bi.min, _bi.max, _bi.round, _bi.abs


# ----------------------------------------------------------------------------- args
def arg(key, default=None):
    for a in sys.argv:
        if a.startswith(key + ':') or a.startswith(key + '='):
            return a[len(key) + 1:]
    return default


CAE = [a for a in sys.argv if a.lower().endswith('.cae')]
if CAE:
    openMdb(pathName=CAE[-1])
MODEL_FILTER, PART_FILTER, EXPORT = arg('model'), arg('part'), ('export' in sys.argv)
outdir = os.path.dirname(mdb.pathName) if mdb.pathName else os.getcwd()

TXT = []


def w(*a):
    s = ' '.join(str(x) for x in a)
    TXT.append(s)
    sys.__stdout__.write(s + '\n')
    sys.__stdout__.flush()


def safe(f, *a, **k):
    try:
        return f(*a, **k)
    except Exception as e:
        return 'ERR: %s' % e


# ----------------------------------------------------------------------------- element metrics
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def norm(a): return math.sqrt(dot(a, a))


def ang(u, v):
    nu, nv = norm(u), norm(v)
    if nu == 0 or nv == 0:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(u, v) / (nu * nv)))))


TOPO = {   # linear corner topology in Abaqus node order
    8: dict(faces=[(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)],
            edges=[(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]),
    6: dict(faces=[(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)],
            edges=[(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (0, 3), (1, 4), (2, 5)]),
    4: dict(faces=[(0, 1, 2), (0, 3, 1), (1, 3, 2), (2, 3, 0)],
            edges=[(0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3)]),
}
CORNERS = {20: 8, 27: 8, 15: 6, 10: 4}
HEX_NB = {0: (1, 3, 4), 1: (2, 0, 5), 2: (3, 1, 6), 3: (0, 2, 7), 4: (7, 5, 0), 5: (4, 6, 1), 6: (5, 7, 2), 7: (6, 4, 3)}


def shell_corners(n):
    return 4 if n in (4, 8, 9) else 3 if n in (3, 6) else n


def elem_metrics(xyz, solid):
    n = CORNERS.get(len(xyz), len(xyz)) if solid else shell_corners(len(xyz))
    xyz = xyz[:n]
    if not solid:   # shells: one polygon
        k = len(xyz)
        angs = [ang(sub(xyz[i - 1], xyz[i]), sub(xyz[(i + 1) % k], xyz[i])) for i in range(k)]
        L = [norm(sub(xyz[i], xyz[(i + 1) % k])) for i in range(k)]
        return dict(minAngle=round(min(angs), 2), maxAngle=round(max(angs), 2),
                    aspect=round(max(L) / min(L), 2) if min(L) > 0 else 1e9)
    t = TOPO.get(n)
    if t is None:
        return {}
    angs = []
    for f in t['faces']:
        k = len(f)
        for i in range(k):
            p, a, b = xyz[f[i]], xyz[f[i - 1]], xyz[f[(i + 1) % k]]
            angs.append(ang(sub(a, p), sub(b, p)))
    L = [norm(sub(xyz[i], xyz[j])) for i, j in t['edges']]
    m = dict(minAngle=round(min(angs), 2), maxAngle=round(max(angs), 2),
             aspect=round(max(L) / min(L), 2) if min(L) > 0 else 1e9)
    if n == 8:
        sj = []
        for c, (i, j, k) in HEX_NB.items():
            u, v, ww = sub(xyz[i], xyz[c]), sub(xyz[j], xyz[c]), sub(xyz[k], xyz[c])
            d = norm(u) * norm(v) * norm(ww)
            sj.append(dot(cross(u, v), ww) / d if d else 0.0)
        m['minScaledJac'] = round(min(sj), 3)
    return m


def count(r, key):
    try:
        return len(r[key])
    except Exception:
        return 0


# ----------------------------------------------------------------------------- per part
def diagnose(mname, part):
    rep = {}
    solid = len(part.cells) > 0
    w('-' * 78)
    w('PART %s/%s  %s  cells=%d faces=%d edges=%d nodes=%d elements=%d' % (
        mname, part.name, 'solid' if solid else 'shell/orphan', len(part.cells), len(part.faces),
        len(part.edges), len(part.nodes), len(part.elements)))
    rep['counts'] = dict(cells=len(part.cells), faces=len(part.faces), edges=len(part.edges),
                         nodes=len(part.nodes), elements=len(part.elements))

    # geometry: free edges (an edge with one face on a shell part = an unconnected panel border)
    free = []
    for e in part.edges:
        if len(e.getFaces()) == 1:
            L = safe(e.getSize, printResults=False)
            free.append((L if isinstance(L, float) else 0.0, e.pointOn[0]))
    rep['geometry_free_edges'] = dict(n=len(free), total_length=sum(f[0] for f in free),
                                      sample=[f[1] for f in free[:20]])
    if len(part.faces):
        w('  geometry free edges: %d (total length %.4g). On a closed solid this must be 0; on a shell '
          'model every internal joint should be shared.' % (len(free), sum(f[0] for f in free)))
    before = set(part.sets.keys())
    chk = safe(part.checkGeometry, detailed=ON)
    new_sets = [s for s in part.sets.keys() if s not in before]
    rep['checkGeometry'] = dict(result=str(chk), problem_sets=new_sets)
    for s in new_sets:
        del part.sets[s]
    if new_sets:
        w('  checkGeometry flagged: %s  (invalid / imprecise entities: repair before meshing)' % new_sets)
    elens = []
    for e in part.edges:
        L = safe(e.getSize, printResults=False)
        if isinstance(L, float):
            elens.append((L, e.index, e.pointOn[0]))
    elens.sort()
    rep['shortest_edges'] = [dict(length=L, index=i, point=p) for L, i, p in elens[:25]]
    if elens:
        w('  edge length min=%.4g median=%.4g max=%.4g  (min << median means sliver geometry)'
          % (elens[0][0], elens[len(elens) // 2][0], elens[-1][0]))

    # mesh controls per cell
    tech = {}
    cells = []
    for c in part.cells:
        sh = str(safe(lambda: part.getMeshControl(c, ELEM_SHAPE)))
        tq = str(safe(lambda: part.getMeshControl(c, TECHNIQUE)))
        tech['%s/%s' % (sh, tq)] = tech.get('%s/%s' % (sh, tq), 0) + 1
        cells.append(dict(index=c.index, shape=sh, technique=tq))
    rep['cell_controls'] = tech
    if tech:
        w('  cell controls: %s' % tech)

    if not len(part.elements):
        w('  (not meshed)')
        return rep

    # Abaqus checks
    bad = {}
    vr = safe(part.verifyMeshQuality, criterion=ANALYSIS_CHECKS)
    if isinstance(vr, dict):
        rep['analysis_checks'] = dict(errors=count(vr, 'failedElements'), warnings=count(vr, 'warningElements'))
        for key in ('failedElements', 'warningElements'):
            for el in vr.get(key, ()) or ():
                bad.setdefault(el.label, []).append('ANALYSIS:' + key[:4])
    w('  ANALYSIS_CHECKS: %s' % rep.get('analysis_checks', vr))
    shape = {}
    for crit, thr in (('SMALL_ANGLE', 10.0), ('LARGE_ANGLE', 160.0), ('ASPECT_RATIO', 10.0),
                      ('SHAPE_FACTOR', 0.0001), ('GEOM_DEVIATION_FACTOR', 0.2)):
        r = safe(lambda: part.verifyMeshQuality(criterion=globals()[crit], threshold=thr))
        shape[crit] = count(r, 'failedElements') if isinstance(r, dict) else str(r)
        if isinstance(r, dict):
            for el in r.get('failedElements', ()) or ():
                bad.setdefault(el.label, []).append(crit)
    rep['shape_metrics'] = shape
    w('  shape metrics (failed at dialog defaults): %s' % shape)

    # element -> cell, bad elements grouped by cell
    el2cell = {}
    for c in part.cells:
        sn = '__diag_c%d' % c.index
        s = part.Set(name=sn, cells=part.cells[c.index:c.index + 1])
        for el in s.elements:
            el2cell[el.label] = c.index
        del part.sets[sn]
    lab2el = dict((el.label, el) for el in part.elements) if bad else {}
    rows = []
    for lab, crits in sorted(bad.items()):
        el = lab2el[lab]
        xyz = [n.coordinates for n in el.getNodes()]
        cen = tuple(round(sum(p[i] for p in xyz) / len(xyz), 6) for i in range(3))
        r = dict(label=lab, fails=crits, type=str(el.type), cell=el2cell.get(lab), centroid=cen)
        r.update(elem_metrics(xyz, solid))
        rows.append(r)
    rep['bad_elements'] = rows
    bycell = {}
    for r in rows:
        bycell.setdefault(r['cell'], []).append(r)
    rep['bad_cells'] = {}
    w('  bad elements: %d in %d cells' % (len(rows), len(bycell)))
    for ci, rs in sorted(bycell.items(), key=lambda kv: -len(kv[1])):
        info = dict(n=len(rs), worstMinAngle=min(r.get('minAngle', 999) for r in rs),
                    worstMaxAngle=max(r.get('maxAngle', 0) for r in rs),
                    worstAspect=max(r.get('aspect', 0) for r in rs))
        if ci is not None:
            c = part.cells[ci]
            info.update(cells[ci])
            info['point_on'] = c.pointOn[0]
            info['edges'] = [dict(index=ei, length=safe(part.edges[ei].getSize, printResults=False),
                                  seeds=str(safe(lambda: part.getEdgeSeeds(part.edges[ei], NUMBER))),
                                  point=part.edges[ei].pointOn[0]) for ei in c.getEdges()]
        rep['bad_cells'][str(ci)] = info
        w('   cell %-5s n=%-4d minAng=%-7s maxAng=%-7s AR=%-7s %s/%s at %s' % (
            ci, len(rs), info['worstMinAngle'], info['worstMaxAngle'], info['worstAspect'],
            info.get('shape'), info.get('technique'), info.get('point_on')))

    # shells: element edge sharing -> free mesh edges and T-junctions
    if not solid:
        use = {}
        for el in part.elements:
            cn = el.connectivity
            k = shell_corners(len(cn))
            for i in range(k):
                a, b = cn[i], cn[(i + 1) % k]
                key = (min(a, b), max(a, b))
                use[key] = use.get(key, 0) + 1
        hist = {}
        for v in use.values():
            hist[v] = hist.get(v, 0) + 1
        rep['shell_edge_sharing'] = hist
        w('  shell element-edge sharing (1 = free, 2 = normal, 3+ = T-junction): %s' % hist)
    return rep


report = {'cae': mdb.pathName, 'release': str(globals().get('version', 'unknown')), 'models': {}}
for mname, model in mdb.models.items():
    if MODEL_FILTER and mname != MODEL_FILTER:
        continue
    report['models'][mname] = {}
    w('=' * 78)
    w('MODEL %s' % mname)
    for pname, part in model.parts.items():
        if PART_FILTER and pname != PART_FILTER:
            continue
        report['models'][mname][pname] = diagnose(mname, part)
        if EXPORT and len(part.faces):
            base = os.path.join(outdir, ('%s_%s' % (mname, pname)).replace(' ', '_').replace('-', '_'))
            safe(part.writeAcisFile, base + '.sat')
            safe(part.writeStepFile, base + '.stp')

with open(os.path.join(outdir, 'mesh_report.json'), 'w') as fh:
    json.dump(report, fh, indent=1, default=str)
with open(os.path.join(outdir, 'mesh_report.txt'), 'w') as fh:
    fh.write('\n'.join(TXT) + '\n')
w('wrote mesh_report.txt / mesh_report.json to %s (the .cae was NOT saved)' % outdir)
