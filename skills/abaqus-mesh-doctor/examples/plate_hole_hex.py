# -*- coding: utf-8 -*-
"""
plate_hole_hex.py - textbook worked example for abaqus-mesh-doctor: quarter model of a plate with
a central hole under uniaxial tension, partitioned "butterfly" style so it meshes as a clean
STRUCTURED hex mesh, then checked with Analysis Checks and (optionally) solved.

    abaqus cae noGUI=plate_hole_hex.py              # build + mesh + verify, write plate_hole.inp
    abaqus cae noGUI=plate_hole_hex.py -- submit    # ... and run the job

Units: mm, N, MPa.  Public textbook problem (Kirsch / Peterson), no project data.

Why the partition matters: the quarter plate is a 5-sided region (two symmetry edges, two outer
edges, the hole arc). Swept/structured hex needs 4-sided faces, so one cut from the hole to the
outer corner (the "butterfly" diagonal) splits it into two 4-sided cells. Without the cut Abaqus
colours the region yellow/orange (sweep with distortion or tet only).

Expected (hand calc, see README.md): sigma_xx max at the hole edge on the y axis
~ 300-320 MPa for 100 MPa remote tension (Kt gross 3.0 infinite plate; finite-width Heywood
Kt_net = 2 + (1 - d/W)^3 = 2.51 on net stress 125 MPa -> 314 MPa).
Verified on Abaqus 2023: 2 cells, 0 non-hex elements, 0 Analysis Checks errors/warnings,
S11 max 319.9 MPa (Kt 3.20) and RF1 = -50 000 N. See README.md.

Python 2.7 and 3.  OhmFrame - https://ohmframe.com - MIT licence.
"""
from __future__ import print_function

import math
import sys

from abaqus import *
from abaqusConstants import *
from caeModules import *
import mesh
try:
    import builtins as _bi
except ImportError:
    import __builtin__ as _bi
sum, min, max, round, abs = _bi.sum, _bi.min, _bi.max, _bi.round, _bi.abs

# ---------------------------------------------------------------- parameters
W, H, T = 200.0, 200.0, 5.0          # full plate width, height, thickness
D = 40.0                            # hole diameter
SIGMA = 100.0                       # remote tension (MPa) on the x faces
E, NU = 210000.0, 0.3
SEED_ARC = 24                       # elements along the quarter hole arc (two cells x 12)
SEED_GLOBAL = 4.0
N_THICK = 2                         # elements through the thickness
JOB = 'plate_hole'
SUBMIT = 'submit' in sys.argv


def log(s):
    sys.__stdout__.write(str(s) + '\n')
    sys.__stdout__.flush()


R, A, B = D / 2.0, W / 2.0, H / 2.0
mdb.Model(name='PLATE_HOLE', modelType=STANDARD_EXPLICIT)
mo = mdb.models['PLATE_HOLE']
if 'Model-1' in mdb.models.keys() and len(mdb.models) > 1:
    del mdb.models['Model-1']

# ---------------------------------------------------------------- geometry: quarter plate
sk = mo.ConstrainedSketch(name='quarter', sheetSize=4 * max(A, B))
sk.Line(point1=(R, 0.0), point2=(A, 0.0))
sk.Line(point1=(A, 0.0), point2=(A, B))
sk.Line(point1=(A, B), point2=(0.0, B))
sk.Line(point1=(0.0, B), point2=(0.0, R))
sk.ArcByCenterEnds(center=(0.0, 0.0), point1=(R, 0.0), point2=(0.0, R), direction=COUNTERCLOCKWISE)
p = mo.Part(name='PLATE', dimensionality=THREE_D, type=DEFORMABLE_BODY)
p.BaseSolidExtrude(sketch=sk, depth=T)

# ---------------------------------------------------------------- butterfly partition
# plane through the hole axis (0,0,z) and the outer corner (A,B)
p.PartitionCellByPlaneThreePoints(cells=p.cells, point1=(0.0, 0.0, 0.0), point2=(0.0, 0.0, T),
                                  point3=(A, B, 0.0))
log('cells after butterfly cut: %d (expect 2)' % len(p.cells))

# ---------------------------------------------------------------- material, section
mat = mo.Material(name='STEEL')
mat.Elastic(table=((E, NU),))
mo.HomogeneousSolidSection(name='SEC', material='STEEL')
p.SectionAssignment(region=p.Set(name='ALL', cells=p.cells), sectionName='SEC')

# ---------------------------------------------------------------- mesh: structured hex
p.setMeshControls(regions=p.cells, elemShape=HEX, technique=STRUCTURED)
p.setElementType(regions=(p.cells,), elemTypes=(mesh.ElemType(elemCode=C3D8I, elemLibrary=STANDARD),))
p.seedPart(size=SEED_GLOBAL, deviationFactor=0.1, minSizeFactor=0.1)
# Structured meshing needs equal element counts on opposite edges of every 4-sided face:
#   hole arc (each half)  <->  outer edge (x = A or y = B)      -> N_ARC each
#   radial edge on a symmetry plane  <->  butterfly diagonal    -> N_RAD each, biased to the hole
N_ARC = SEED_ARC // 2
N_RAD = int(round((max(A, B) - R) / SEED_GLOBAL / 1.5))
c45 = math.radians(22.5)
for z in (0.0, T):
    arcs = p.edges.findAt(((R * math.cos(c45), R * math.sin(c45), z),),
                          ((R * math.sin(c45), R * math.cos(c45), z),))
    outer = p.edges.findAt(((A, 0.5 * B, z),), ((0.5 * A, B, z),))
    p.seedEdgeByNumber(edges=arcs, number=N_ARC, constraint=FIXED)
    p.seedEdgeByNumber(edges=outer, number=N_ARC, constraint=FIXED)
    for pt in ((0.5 * (R + A), 0.0, z), (0.0, 0.5 * (R + B), z),
               (0.5 * (R * math.cos(math.radians(45)) + A), 0.5 * (R * math.sin(math.radians(45)) + B), z)):
        e = p.edges.findAt((pt,))[0]
        v0 = p.vertices[e.getVertices()[0]].pointOn[0]
        ea = p.edges[e.index:e.index + 1]
        # put the small elements at the hole end, whichever way the edge is oriented
        if math.hypot(v0[0], v0[1]) < R + 1e-6:
            p.seedEdgeByBias(biasMethod=SINGLE, end1Edges=ea, ratio=4.0, number=N_RAD, constraint=FIXED)
        else:
            p.seedEdgeByBias(biasMethod=SINGLE, end2Edges=ea, ratio=4.0, number=N_RAD, constraint=FIXED)
thick_pts = []
for e in p.edges:
    vs = e.getVertices()
    if len(vs) == 2:
        z0 = p.vertices[vs[0]].pointOn[0][2]
        z1 = p.vertices[vs[1]].pointOn[0][2]
        if abs(abs(z1 - z0) - T) < 1e-6:
            thick_pts.append((e.pointOn[0],))
p.seedEdgeByNumber(edges=p.edges.findAt(*thick_pts), number=N_THICK, constraint=FIXED)
p.generateMesh()
q = p.verifyMeshQuality(criterion=ANALYSIS_CHECKS)
log('mesh: %d elements, %d nodes; analysis checks errors=%d warnings=%d'
    % (len(p.elements), len(p.nodes), len(q['failedElements']), len(q['warningElements'])))
non_hex = sum(1 for el in p.elements if len(el.connectivity) != 8)
log('non-hex elements: %d (expect 0)' % non_hex)

# ---------------------------------------------------------------- assembly, step, BCs, load
a = mo.rootAssembly
a.DatumCsysByDefault(CARTESIAN)
inst = a.Instance(name='PLATE-1', part=p, dependent=ON)
eps = 1e-6
f_x0 = inst.faces.getByBoundingBox(-eps, -eps, -eps, eps, B + eps, T + eps)       # x = 0  symmetry
f_y0 = inst.faces.getByBoundingBox(-eps, -eps, -eps, A + eps, eps, T + eps)       # y = 0  symmetry
f_z0 = inst.faces.getByBoundingBox(-eps, -eps, -eps, A + eps, B + eps, eps)       # z = 0  (plane stress-like)
f_load = inst.faces.getByBoundingBox(A - eps, -eps, -eps, A + eps, B + eps, T + eps)
for nm, fs in (('X0', f_x0), ('Y0', f_y0), ('Z0', f_z0)):
    if len(fs) == 0:
        raise RuntimeError('empty selection for %s - geometry changed?' % nm)
    a.Set(name=nm, faces=fs)
a.Surface(name='LOAD', side1Faces=f_load)
hole_nodes = [n for n in inst.nodes if abs(n.coordinates[0]) < eps and abs(n.coordinates[1] - R) < 1e-3]
if not hole_nodes:
    raise RuntimeError('no nodes found at the hole edge on the y axis')
a.Set(name='HOLE_TOP', nodes=inst.nodes.sequenceFromLabels([n.label for n in hole_nodes]))

mo.StaticStep(name='TENSION', previous='Initial', nlgeom=OFF)
mo.XsymmBC(name='SYM_X', createStepName='Initial', region=a.sets['X0'])
mo.YsymmBC(name='SYM_Y', createStepName='Initial', region=a.sets['Y0'])
mo.ZsymmBC(name='SYM_Z', createStepName='Initial', region=a.sets['Z0'])
mo.Pressure(name='TENSION', createStepName='TENSION', region=a.surfaces['LOAD'], magnitude=-SIGMA)
mo.fieldOutputRequests['F-Output-1'].setValues(variables=('S', 'U', 'RF', 'E'))
mo.HistoryOutputRequest(name='H-HOLE', createStepName='TENSION', variables=('S11',),
                        region=a.sets['HOLE_TOP'])

job = mdb.Job(name=JOB, model='PLATE_HOLE')
job.writeInput(consistencyChecking=OFF)
mdb.saveAs(pathName=JOB + '.cae')
log('wrote %s.inp and %s.cae' % (JOB, JOB))
if SUBMIT:
    job.submit(consistencyChecking=OFF)
    job.waitForCompletion()
    log('job finished - post-process with abaqus-odb-extract:')
    log('  abaqus python odb_extract.py %s.odb --field S:S11 --region HOLE_TOP --out results' % JOB)
