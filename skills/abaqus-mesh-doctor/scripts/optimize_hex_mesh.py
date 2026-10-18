# -*- coding: utf-8 -*-
"""
optimize_hex_mesh.py - clear Abaqus "Analysis Checks" warnings/errors on a native linear hex
mesh (C3D8, C3D8R, C3D8I, DC3D8 ...) by relocating nodes. Geometry is not changed: every moved
node goes through Part.editNode(..., projectToGeometry=ON), so nodes on faces/edges stay there.

    abaqus cae noGUI=optimize_hex_mesh.py -- cae:model.cae model:Model-1 part:Part-1 out:model_opt.cae [passes:10]
    (GUI: set MODEL_NAME / PART below, then File > Run Script)

Per node it tries Laplacian moves, a numerical-gradient step on a quality score and a few
random moves, and keeps a move only if the worst element around the node improves. The score
combines the Analysis Checks isoparametric angles (45..135 deg), the Verify-Mesh face corner
angles (10..160 deg) and a positive scaled Jacobian.

Notes
  * Run it AFTER the mesh is final. Re-meshing or re-seeding the part discards the moves.
  * Native (geometry) parts only; for orphan meshes drop projectToGeometry.
  * Check afterwards: Mesh > Verify > Analysis Checks, and abaqus-mesh-doctor/mesh_diagnose.py.

Python 2.7 and 3.  OhmFrame - https://ohmframe.com - MIT licence.
"""
from __future__ import print_function

import math
import random
import sys

from abaqus import *
from abaqusConstants import *
import part
import mesh
try:
    import builtins as _bi
except ImportError:
    import __builtin__ as _bi
sum, min, max, round, abs = _bi.sum, _bi.min, _bi.max, _bi.round, _bi.abs

MODEL_NAME, PART, CAE, OUT, PASSES = 'Model-1', 'Part-1', None, None, 10
for a in sys.argv:          # key:value or key=value
    for key in ('model', 'part', 'cae', 'out', 'passes'):
        if a.startswith(key + '=') or a.startswith(key + ':'):
            val = a[len(key) + 1:]
            if key == 'model':
                MODEL_NAME = val
            elif key == 'part':
                PART = val
            elif key == 'cae':
                CAE = val
            elif key == 'out':
                OUT = val
            else:
                PASSES = int(val)
if CAE:
    openMdb(pathName=CAE)
p = mdb.models[MODEL_NAME].parts[PART]


def log(s):
    sys.__stdout__.write(s + '\n')
    sys.__stdout__.flush()


F = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
PAIRS = ((0, 1), (2, 4), (3, 5))
EDG = ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7))
NBR = {0: (1, 3, 4), 1: (2, 0, 5), 2: (3, 1, 6), 3: (0, 2, 7), 4: (7, 5, 0), 5: (4, 6, 1), 6: (5, 7, 2), 7: (6, 4, 3)}
coord, econn, n2e = {}, {}, {}


def load_elem(e):
    if e.label in econn:
        return
    ns = e.getNodes()
    if len(ns) != 8:
        return
    econn[e.label] = [n.label for n in ns]
    for n in ns:
        if n.label not in coord:
            coord[n.label] = list(n.coordinates)
        n2e.setdefault(n.label, set()).add(e.label)


def _ang(u, v):
    nu = math.sqrt(sum(x * x for x in u))
    nv = math.sqrt(sum(x * x for x in v))
    if nu == 0 or nv == 0:
        return None
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(u[k] * v[k] for k in range(3)) / (nu * nv)))))


def quality(el, ov=None):
    """Margin to the nearest limit (deg-like units); negative = the element fails a check."""
    X = [ov[l] if (ov and l in ov) else coord[l] for l in econn[el]]
    Cf = [[(X[f[0]][k] + X[f[1]][k] + X[f[2]][k] + X[f[3]][k]) / 4.0 for k in range(3)] for f in F]
    L = [[Cf[b][k] - Cf[a_][k] for k in range(3)] for a_, b in PAIRS]
    mval = 1e9
    for i, j in ((0, 1), (0, 2), (1, 2)):                 # isoparametric angles, Analysis Checks 45..135
        a = _ang(L[i], L[j])
        if a is None:
            return -90.0
        mval = min(mval, a - 45.0, 135.0 - a)
    for fc in F:                                          # face corner angles, Verify Mesh 10..160
        for q in range(4):
            pa, pb, pc = X[fc[q - 1]], X[fc[q]], X[fc[(q + 1) % 4]]
            a = _ang([pa[k] - pb[k] for k in range(3)], [pc[k] - pb[k] for k in range(3)])
            if a is None:
                return -90.0
            mval = min(mval, a - 12.0, 158.0 - a)
    for c0, (i, j, k) in NBR.items():                     # keep the scaled Jacobian positive
        u = [X[i][q] - X[c0][q] for q in range(3)]
        v = [X[j][q] - X[c0][q] for q in range(3)]
        w_ = [X[k][q] - X[c0][q] for q in range(3)]
        cr = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        den = math.sqrt(sum(x * x for x in u)) * math.sqrt(sum(x * x for x in v)) * math.sqrt(sum(x * x for x in w_))
        sj = sum(cr[q] * w_[q] for q in range(3)) / den if den else -1.0
        if sj < 0.15:
            mval = min(mval, -50.0 + 100.0 * sj)
    return mval


def node_score(nl, pos=None):
    ov = {nl: pos} if pos is not None else None
    return min(quality(el, ov) for el in n2e[nl])


def neighbours(nl):
    out = set()
    for el in n2e[nl]:
        cn = econn[el]
        i = cn.index(nl)
        for a_, b in EDG:
            if a_ == i:
                out.add(cn[b])
            elif b == i:
                out.add(cn[a_])
    return out


def move(nl, pos):
    p.editNode(nodes=p.nodes.sequenceFromLabels((nl,)), coordinate1=pos[0], coordinate2=pos[1],
               coordinate3=pos[2], projectToGeometry=ON)
    coord[nl] = list(p.nodes.getFromLabel(nl).coordinates)


def bad_list():
    rq = p.verifyMeshQuality(criterion=ANALYSIS_CHECKS)
    extra = list(p.verifyMeshQuality(criterion=LARGE_ANGLE, threshold=160.0)['failedElements']) + \
        list(p.verifyMeshQuality(criterion=SMALL_ANGLE, threshold=10.0)['failedElements'])
    hexes = [e for e in list(rq['warningElements']) + list(rq['failedElements']) + extra
             if len(e.connectivity) == 8]
    return hexes, len(rq['warningElements']), len(rq['failedElements']), len(extra)


random.seed(1)
bad, nw, nf, nx = bad_list()
log('start: analysis warnings=%d errors=%d shape-angle failures=%d' % (nw, nf, nx))
for ps in range(PASSES):
    if nw + nf + nx == 0:
        break
    for e in bad:
        load_elem(e)
    nodes = set()
    for e in bad:
        nodes.update(econn.get(e.label, []))
    for nl in list(nodes):
        for el in p.nodes.getFromLabel(nl).getElements():
            load_elem(el)
    nodes = [nl for nl in nodes if all(el in econn for el in n2e.get(nl, ()))]
    moved = 0
    for nl in sorted(nodes, key=node_score):
        s0 = node_score(nl)
        if s0 > 3.0:
            continue
        x0 = coord[nl][:]
        nbs = neighbours(nl)
        lap = [sum(coord[q][k] for q in nbs) / len(nbs) for k in range(3)]
        h = 0.25 * min(math.sqrt(sum((coord[q][k] - x0[k]) ** 2 for k in range(3))) for q in nbs)
        cands = [[x0[k] + tt * (lap[k] - x0[k]) for k in range(3)] for tt in (0.25, 0.5, 0.75, 1.0)]
        gr = []
        for k in range(3):
            xp = x0[:]; xp[k] += h * 0.05
            xm = x0[:]; xm[k] -= h * 0.05
            gr.append((node_score(nl, xp) - node_score(nl, xm)) / (h * 0.1))
        gn = math.sqrt(sum(x * x for x in gr))
        if gn > 0:
            cands += [[x0[k] + tt * h * gr[k] / gn for k in range(3)] for tt in (0.1, 0.25, 0.5, 1.0, 2.0)]
        cands += [[x0[k] + random.uniform(-1, 1) * h * 0.6 for k in range(3)] for _ in range(6)]
        best, bs = None, s0
        for cnd in cands:
            sc = node_score(nl, cnd)
            if sc > bs + 1e-3:
                bs, best = sc, cnd
        if best is None:
            continue
        move(nl, best)                       # projection can change the position: re-check
        if node_score(nl) < s0 - 1e-6:
            move(nl, x0)
        else:
            moved += 1
    bad, nw, nf, nx = bad_list()
    log('pass %d: nodes moved=%d  analysis warnings=%d errors=%d shape-angle failures=%d'
        % (ps, moved, nw, nf, nx))
log('done. Verify with Mesh > Verify > Analysis Checks.')
if OUT:
    mdb.saveAs(pathName=OUT)
    log('saved %s' % OUT)
