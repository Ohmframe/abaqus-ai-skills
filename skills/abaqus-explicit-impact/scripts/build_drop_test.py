# -*- coding: utf-8 -*-
"""
build_drop_test.py - generic Abaqus/Explicit impact template: a rigid sphere (impactor) hits a
clamped deformable plate. Every number lives in the PARAMETERS block; change them, not the code.
The default values are a public textbook-style check case, not project data.

    abaqus cae noGUI=build_drop_test.py              # build + write drop_test.inp/.cae
    abaqus cae noGUI=build_drop_test.py -- submit    # ... and run (cpus from CPUS)
    then:  abaqus python energy_balance.py drop_test.odb --mode impact

Units: mm, tonne, s, N, MPa, mJ (N.mm).  Density 7.85e-9 t/mm^3 for steel.

Model
  * plate: S4R shells (SC8R/C3D8R thick plates: change PLATE_TYPE), elastic-plastic, all four edges encastre
  * impactor: discrete rigid revolved sphere (R3D4), rigid body tied to a reference point that
    carries the mass and rotary inertia; initial velocity on the RP; optional gravity
  * general contact (all with self), penalty friction
  * history: whole-model energies every DT_HIST, RP displacement/velocity/reaction-free contact force
  * optional element deletion (ductile damage) and semi-automatic mass scaling (OFF by default:
    an impact is a dynamic event - mass scaling changes the answer, check DMASS if you use it)

Hand check for the defaults (examples/README.md): KE0 = 0.5 * m * v^2 = 12 500 mJ; the
energy balance must hold (ETOTAL ~ constant, within ~1-2 % of KE0).
Untested on Abaqus - verify before relying on it.

Python 2.7 and 3.  OhmFrame - https://ohmframe.com - MIT licence.
"""
from __future__ import print_function

import math
import sys

from abaqus import *
from abaqusConstants import *
from caeModules import *
import mesh
import regionToolset
try:
    import builtins as _bi
except ImportError:
    import __builtin__ as _bi
sum, min, max, round, abs = _bi.sum, _bi.min, _bi.max, _bi.round, _bi.abs

# ============================================================== PARAMETERS
MODEL_NAME = 'DROP_TEST'
JOB = 'drop_test'
CPUS = 1
# plate
PLATE_L, PLATE_W, PLATE_T = 200.0, 200.0, 2.0
PLATE_SEED = 4.0
PLATE_TYPE = 'S4R'                    # S4R (shell) or C3D8R (solid, needs >= 3 through thickness)
N_THICK_SOLID = 3
RHO, E, NU = 7.85e-9, 210000.0, 0.3
PLASTIC = ((250.0, 0.0), (300.0, 0.05), (400.0, 0.20))     # true stress (MPa), plastic strain; () = elastic
DAMAGE = None                         # e.g. dict(strain=0.3, triax=0.33, rate=1.0, disp=0.5) -> elements deleted
# impactor
SPHERE_R = 25.0
MASS = 1.0e-3                         # tonne (= 1 kg)
V0 = 5000.0                           # mm/s (= 5 m/s), downward (-Z)
GAP = 0.5                             # initial clearance above the plate (mm)
GRAVITY = False                       # True: -9810 mm/s^2 on everything
FRICTION = 0.2
# step
T_END = 3.0e-3                        # s
DT_HIST = T_END / 300.0
N_FIELD = 30
MASS_SCALING_DT = None                # e.g. 1e-7 -> semi-automatic, below-min only
DOUBLE_PRECISION = False              # use True for > ~300k increments (energy drift)
SUBMIT = 'submit' in sys.argv
# ============================================================== END PARAMETERS


def log(s):
    sys.__stdout__.write(str(s) + '\n')
    sys.__stdout__.flush()


mo = mdb.Model(name=MODEL_NAME, modelType=STANDARD_EXPLICIT)
if 'Model-1' in mdb.models.keys():
    del mdb.models['Model-1']

# ---------------------------------------------------------------- plate
sk = mo.ConstrainedSketch(name='plate', sheetSize=4 * max(PLATE_L, PLATE_W))
sk.rectangle(point1=(-PLATE_L / 2, -PLATE_W / 2), point2=(PLATE_L / 2, PLATE_W / 2))
plate = mo.Part(name='PLATE', dimensionality=THREE_D, type=DEFORMABLE_BODY)
solid = PLATE_TYPE.upper().startswith('C3D')
if solid:
    plate.BaseSolidExtrude(sketch=sk, depth=PLATE_T)      # occupies z in [0, T]
    top_z = PLATE_T
else:
    plate.BaseShell(sketch=sk)                            # mid-surface at z = 0
    top_z = PLATE_T / 2.0

mat = mo.Material(name='PLATE_MAT')
mat.Density(table=((RHO,),))
mat.Elastic(table=((E, NU),))
if PLASTIC:
    mat.Plastic(table=PLASTIC)
if DAMAGE:
    mat.DuctileDamageInitiation(table=((DAMAGE['strain'], DAMAGE['triax'], DAMAGE['rate']),))
    mat.ductileDamageInitiation.DamageEvolution(type=DISPLACEMENT, table=((DAMAGE['disp'],),))
if solid:
    mo.HomogeneousSolidSection(name='PLATE_SEC', material='PLATE_MAT')
    region = plate.Set(name='ALL', cells=plate.cells)
else:
    mo.HomogeneousShellSection(name='PLATE_SEC', material='PLATE_MAT', thickness=PLATE_T,
                               numIntPts=5)
    region = plate.Set(name='ALL', faces=plate.faces)
plate.SectionAssignment(region=region, sectionName='PLATE_SEC')

kw = dict(elemLibrary=EXPLICIT, hourglassControl=ENHANCED)
if DAMAGE:
    kw.update(elemDeletion=ON, maxDegradation=0.99)
if solid:
    plate.setElementType(regions=(plate.cells,), elemTypes=(mesh.ElemType(elemCode=C3D8R, secondOrderAccuracy=OFF,
                                                                          kinematicSplit=AVERAGE_STRAIN, **kw),))
    plate.seedPart(size=PLATE_SEED)
    tz = [e for e in plate.edges
          if abs(abs(plate.vertices[e.getVertices()[0]].pointOn[0][2] -
                     plate.vertices[e.getVertices()[1]].pointOn[0][2]) - PLATE_T) < 1e-6]
    plate.seedEdgeByNumber(edges=plate.edges.findAt(*[(e.pointOn[0],) for e in tz]), number=N_THICK_SOLID,
                           constraint=FIXED)
else:
    plate.setMeshControls(regions=plate.faces, elemShape=QUAD, technique=STRUCTURED)
    plate.setElementType(regions=(plate.faces,), elemTypes=(mesh.ElemType(elemCode=S4R, **kw),))
    plate.seedPart(size=PLATE_SEED)
plate.generateMesh()

# ---------------------------------------------------------------- impactor (discrete rigid sphere)
sks = mo.ConstrainedSketch(name='sphere', sheetSize=10 * SPHERE_R)
sks.ConstructionLine(point1=(0.0, -2 * SPHERE_R), point2=(0.0, 2 * SPHERE_R))
sks.ArcByCenterEnds(center=(0.0, 0.0), point1=(0.0, -SPHERE_R), point2=(0.0, SPHERE_R), direction=COUNTERCLOCKWISE)
sph = mo.Part(name='IMPACTOR', dimensionality=THREE_D, type=DISCRETE_RIGID_SURFACE)
sph.BaseShellRevolve(sketch=sks, angle=360.0, flipRevolveDirection=OFF)
sph.setElementType(regions=(sph.faces,), elemTypes=(mesh.ElemType(elemCode=R3D4, elemLibrary=EXPLICIT),
                                                     mesh.ElemType(elemCode=R3D3, elemLibrary=EXPLICIT)))
sph.seedPart(size=min(PLATE_SEED, SPHERE_R / 8.0))
sph.generateMesh()

# ---------------------------------------------------------------- assembly
a = mo.rootAssembly
a.DatumCsysByDefault(CARTESIAN)
ip = a.Instance(name='PLATE-1', part=plate, dependent=ON)
isph = a.Instance(name='IMPACTOR-1', part=sph, dependent=ON)
a.rotate(instanceList=('IMPACTOR-1',), axisPoint=(0, 0, 0), axisDirection=(1, 0, 0), angle=90.0)  # revolve axis Y -> Z
zc = top_z + GAP + SPHERE_R
a.translate(instanceList=('IMPACTOR-1',), vector=(0.0, 0.0, zc))
rp = a.ReferencePoint(point=(0.0, 0.0, zc))
rp_reg = regionToolset.Region(referencePoints=(a.referencePoints[rp.id],))
a.Set(name='RP_IMPACTOR', referencePoints=(a.referencePoints[rp.id],))
a.Surface(name='IMPACTOR_SURF', side1Faces=isph.faces)
mo.RigidBody(name='RB_IMPACTOR', refPointRegion=rp_reg, surfaceRegion=a.surfaces['IMPACTOR_SURF'])
I_sph = 2.0 / 3.0 * MASS * SPHERE_R ** 2               # thin spherical shell; only matters if it rotates
a.engineeringFeatures.PointMassInertia(name='MASS_IMPACTOR', region=a.sets['RP_IMPACTOR'], mass=MASS,
                                       i11=I_sph, i22=I_sph, i33=I_sph, alpha=0.0, composite=0.0)

eps = 1e-3
L2, W2 = PLATE_L / 2.0, PLATE_W / 2.0
zlo, zhi = -PLATE_T, PLATE_T + eps
edge_kind = 'faces' if solid else 'edges'
picked = []
for box in ((-L2 - eps, -W2 - eps, zlo, -L2 + eps, W2 + eps, zhi), (L2 - eps, -W2 - eps, zlo, L2 + eps, W2 + eps, zhi),
            (-L2 - eps, -W2 - eps, zlo, L2 + eps, -W2 + eps, zhi), (-L2 - eps, W2 - eps, zlo, L2 + eps, W2 + eps, zhi)):
    sel = getattr(ip, edge_kind).getByBoundingBox(*box)
    if len(sel) == 0:
        raise RuntimeError('clamp selection empty - check plate geometry')
    picked.append(sel)
if solid:
    a.Set(name='CLAMP', faces=picked[0] + picked[1] + picked[2] + picked[3])
else:
    a.Set(name='CLAMP', edges=picked[0] + picked[1] + picked[2] + picked[3])
centre = [n.label for n in ip.nodes if abs(n.coordinates[0]) < PLATE_SEED / 2 + eps and
          abs(n.coordinates[1]) < PLATE_SEED / 2 + eps]
a.Set(name='PLATE_CENTRE', nodes=ip.nodes.sequenceFromLabels(centre))

# ---------------------------------------------------------------- step, mass scaling
ms = None
if MASS_SCALING_DT:
    ms = ((SEMI_AUTOMATIC, MODEL, AT_BEGINNING, 0.0, MASS_SCALING_DT, BELOW_MIN, 0, 0, 0.0, 0.0, 0, None),)
step_kw = dict(name='IMPACT', previous='Initial', timePeriod=T_END)
if ms:
    step_kw['massScaling'] = ms
mo.ExplicitDynamicsStep(**step_kw)
mo.fieldOutputRequests['F-Output-1'].setValues(variables=('S', 'PEEQ', 'U', 'V', 'RF', 'CSTRESS', 'STATUS', 'EVF')
                                               if DAMAGE else ('S', 'PEEQ', 'U', 'V', 'RF', 'CSTRESS'),
                                               numIntervals=N_FIELD)
mo.historyOutputRequests['H-Output-1'].setValues(variables=('ALLKE', 'ALLIE', 'ALLAE', 'ALLVD', 'ALLFD', 'ALLWK',
                                                            'ALLPD', 'ALLSE', 'ALLDMD', 'ALLMW', 'ETOTAL', 'DMASS'),
                                                 timeInterval=DT_HIST)
mo.HistoryOutputRequest(name='H-IMPACTOR', createStepName='IMPACT', variables=('U3', 'V3', 'A3'),
                        region=a.sets['RP_IMPACTOR'], timeInterval=DT_HIST)
mo.HistoryOutputRequest(name='H-CENTRE', createStepName='IMPACT', variables=('U3',),
                        region=a.sets['PLATE_CENTRE'], timeInterval=DT_HIST)

# ---------------------------------------------------------------- contact, BCs, velocity
cp = mo.ContactProperty('CP_FRIC')
cp.TangentialBehavior(formulation=PENALTY, table=((FRICTION,),), maximumElasticSlip=FRACTION, fraction=0.005)
cp.NormalBehavior(pressureOverclosure=HARD, allowSeparation=ON)
gc = mo.ContactExp(name='GENERAL', createStepName='Initial')
gc.includedPairs.setValuesInStep(stepName='Initial', useAllstar=ON)
gc.contactPropertyAssignments.appendInStep(stepName='Initial', assignments=((GLOBAL, SELF, 'CP_FRIC'),))
mo.EncastreBC(name='CLAMP', createStepName='Initial', region=a.sets['CLAMP'])
mo.Velocity(name='V0', region=a.sets['RP_IMPACTOR'], velocity1=0.0, velocity2=0.0, velocity3=-V0,
            omega=0.0)
if GRAVITY:
    mo.Gravity(name='G', createStepName='IMPACT', comp3=-9810.0)

KE0 = 0.5 * MASS * V0 ** 2
log('plate elements=%d  impactor elements=%d  KE0=%.6g mJ  contact after %.3g s'
    % (len(plate.elements), len(sph.elements), KE0, GAP / V0))
job = mdb.Job(name=JOB, model=MODEL_NAME, numCpus=CPUS, numDomains=CPUS, explicitPrecision=DOUBLE_PLUS_PACK
              if DOUBLE_PRECISION else SINGLE, nodalOutputPrecision=FULL)
job.writeInput(consistencyChecking=OFF)
mdb.saveAs(pathName=JOB + '.cae')
log('wrote %s.inp / %s.cae' % (JOB, JOB))
if SUBMIT:
    job.submit(consistencyChecking=OFF)
    job.waitForCompletion()
    log('done. Check: abaqus python energy_balance.py %s.odb --mode impact --ke0 %.6g' % (JOB, KE0))
