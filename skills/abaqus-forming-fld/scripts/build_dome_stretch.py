# -*- coding: utf-8 -*-
"""
build_dome_stretch.py - generic Abaqus/Explicit sheet-forming template: hemispherical-punch
stretch test (Nakajima-type) on a quarter blank with a locked flange, FLD damage initiation,
energy-based damage evolution and element deletion. Every value is in PARAMETERS.

    abaqus cae noGUI=build_dome_stretch.py              # build, write dome.inp / dome.cae
    abaqus cae noGUI=build_dome_stretch.py -- submit
    then: abaqus python fld_extract.py dome.odb --rp-set RP_PUNCH
          abaqus python ../../abaqus-explicit-impact/scripts/energy_balance.py dome.odb --mode quasistatic

Units: mm, tonne, s, N, MPa.

Simplifications (state them in any report): the flange is locked by a BC on the outer ring instead
of a die + blank holder + draw bead; the punch is a discrete rigid surface; quasi-static loading is
obtained with a SMOOTH_STEP punch stroke over T_END plus optional mass scaling - check ALLKE/ALLIE.
Strain path: STRIP_WIDTH = None gives a full circular blank (biaxial); narrower strips move the
strain path toward uniaxial / plane strain, as in the standard test series.

The default material and FLC are ILLUSTRATIVE (a generic mild-steel-like power law and a
textbook-shaped FLC). Replace them with measured data for any real use.
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
MODEL_NAME, JOB, CPUS = 'DOME', 'dome', 1
R_BLANK = 100.0              # blank radius
R_CLAMP = 80.0               # nodes with r >= R_CLAMP are fixed (locked flange)
STRIP_WIDTH = None           # e.g. 50.0 -> strip |y| <= 25 (quarter: y <= 25); None = full disc
T_SHEET = 1.0
SEED = 2.0
R_PUNCH = 50.0
GAP = 0.2
DEPTH = 40.0                 # punch stroke
FRICTION = 0.05              # lubricated punch
RHO, E, NU = 7.85e-9, 210000.0, 0.3
K_HARD, N_HARD, EPS0 = 500.0, 0.22, 0.005     # sigma = K (eps0 + eps_p)^n  (illustrative)
FLC = ((0.60, -0.30), (0.45, -0.15), (0.30, 0.0), (0.35, 0.15), (0.40, 0.30))   # (major, minor) illustrative
G_FRACTURE = 10.0            # damage evolution energy, mJ/mm^2 (N/mm)
DELETE = True
T_END = 0.02
MASS_SCALING_DT = 5.0e-7     # None = no mass scaling
N_FIELD = 40
SUBMIT = 'submit' in sys.argv
# ============================================================== END PARAMETERS


def log(s):
    sys.__stdout__.write(str(s) + '\n')
    sys.__stdout__.flush()


mo = mdb.Model(name=MODEL_NAME, modelType=STANDARD_EXPLICIT)
if 'Model-1' in mdb.models.keys():
    del mdb.models['Model-1']

# ---------------------------------------------------------------- blank (quarter)
sk = mo.ConstrainedSketch(name='blank', sheetSize=4 * R_BLANK)
if STRIP_WIDTH is None or STRIP_WIDTH / 2.0 >= R_BLANK:
    sk.Line(point1=(0.0, 0.0), point2=(R_BLANK, 0.0))
    sk.ArcByCenterEnds(center=(0.0, 0.0), point1=(R_BLANK, 0.0), point2=(0.0, R_BLANK), direction=COUNTERCLOCKWISE)
    sk.Line(point1=(0.0, R_BLANK), point2=(0.0, 0.0))
else:
    h = STRIP_WIDTH / 2.0
    xe = math.sqrt(R_BLANK ** 2 - h ** 2)
    sk.Line(point1=(0.0, 0.0), point2=(R_BLANK, 0.0))
    sk.ArcByCenterEnds(center=(0.0, 0.0), point1=(R_BLANK, 0.0), point2=(xe, h), direction=COUNTERCLOCKWISE)
    sk.Line(point1=(xe, h), point2=(0.0, h))
    sk.Line(point1=(0.0, h), point2=(0.0, 0.0))
blank = mo.Part(name='BLANK', dimensionality=THREE_D, type=DEFORMABLE_BODY)
blank.BaseShell(sketch=sk)

mat = mo.Material(name='SHEET')
mat.Density(table=((RHO,),))
mat.Elastic(table=((E, NU),))
sy0 = K_HARD * EPS0 ** N_HARD
mat.Plastic(table=tuple((K_HARD * (EPS0 + ep) ** N_HARD, ep) for ep in
                        [0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0]))
mat.FldDamageInitiation(table=FLC)
mat.fldDamageInitiation.DamageEvolution(type=ENERGY, table=((G_FRACTURE,),))
mo.HomogeneousShellSection(name='SHEET_SEC', material='SHEET', thickness=T_SHEET, numIntPts=5)
blank.SectionAssignment(region=blank.Set(name='ALL', faces=blank.faces), sectionName='SHEET_SEC')
et_kw = dict(elemLibrary=EXPLICIT, hourglassControl=ENHANCED)
if DELETE:
    et_kw.update(elemDeletion=ON, maxDegradation=0.99)
blank.setElementType(regions=(blank.faces,), elemTypes=(mesh.ElemType(elemCode=S4R, **et_kw),
                                                         mesh.ElemType(elemCode=S3R, **et_kw)))
blank.setMeshControls(regions=blank.faces, elemShape=QUAD_DOMINATED, technique=FREE)
blank.seedPart(size=SEED)
blank.generateMesh()

# ---------------------------------------------------------------- punch (discrete rigid, revolved)
skp = mo.ConstrainedSketch(name='punch', sheetSize=6 * R_PUNCH)
skp.ConstructionLine(point1=(0.0, -2 * R_PUNCH), point2=(0.0, 2 * R_PUNCH))
skp.ArcByCenterEnds(center=(0.0, 0.0), point1=(0.0, R_PUNCH), point2=(R_PUNCH, 0.0), direction=CLOCKWISE)
skp.Line(point1=(R_PUNCH, 0.0), point2=(R_PUNCH, -0.5 * R_PUNCH))
punch = mo.Part(name='PUNCH', dimensionality=THREE_D, type=DISCRETE_RIGID_SURFACE)
punch.BaseShellRevolve(sketch=skp, angle=360.0, flipRevolveDirection=OFF)
punch.setElementType(regions=(punch.faces,), elemTypes=(mesh.ElemType(elemCode=R3D4, elemLibrary=EXPLICIT),
                                                         mesh.ElemType(elemCode=R3D3, elemLibrary=EXPLICIT)))
punch.seedPart(size=SEED)
punch.generateMesh()

# ---------------------------------------------------------------- assembly
a = mo.rootAssembly
a.DatumCsysByDefault(CARTESIAN)
ib = a.Instance(name='BLANK-1', part=blank, dependent=ON)
ipn = a.Instance(name='PUNCH-1', part=punch, dependent=ON)
a.rotate(instanceList=('PUNCH-1',), axisPoint=(0, 0, 0), axisDirection=(1, 0, 0), angle=90.0)   # sketch Y -> Z
z_apex = -T_SHEET / 2.0 - GAP
a.translate(instanceList=('PUNCH-1',), vector=(0.0, 0.0, z_apex - R_PUNCH))
rp = a.ReferencePoint(point=(0.0, 0.0, z_apex - R_PUNCH))
a.Set(name='RP_PUNCH', referencePoints=(a.referencePoints[rp.id],))
a.Surface(name='PUNCH_SURF', side1Faces=ipn.faces)
mo.RigidBody(name='RB_PUNCH', refPointRegion=regionToolset.Region(referencePoints=(a.referencePoints[rp.id],)),
             surfaceRegion=a.surfaces['PUNCH_SURF'])

eps = 1e-3
clamp = [n.label for n in ib.nodes if math.hypot(n.coordinates[0], n.coordinates[1]) >= R_CLAMP - eps]
if not clamp:
    raise RuntimeError('no nodes beyond R_CLAMP - check R_CLAMP / STRIP_WIDTH')
a.Set(name='CLAMP', nodes=ib.nodes.sequenceFromLabels(clamp))
xsym = ib.edges.getByBoundingBox(-eps, -eps, -eps, eps, R_BLANK + eps, eps)
ysym = ib.edges.getByBoundingBox(-eps, -eps, -eps, R_BLANK + eps, eps, eps)
if len(xsym) == 0 or len(ysym) == 0:
    raise RuntimeError('symmetry edges not found')
a.Set(name='SYM_X', edges=xsym)
a.Set(name='SYM_Y', edges=ysym)
pole = [n.label for n in ib.nodes if math.hypot(n.coordinates[0], n.coordinates[1]) < SEED * 0.75]
a.Set(name='POLE', nodes=ib.nodes.sequenceFromLabels(pole or [ib.nodes[0].label]))

# ---------------------------------------------------------------- step, contact, BCs
step_kw = dict(name='STRETCH', previous='Initial', timePeriod=T_END)
if MASS_SCALING_DT:
    step_kw['massScaling'] = ((SEMI_AUTOMATIC, MODEL, AT_BEGINNING, 0.0, MASS_SCALING_DT, BELOW_MIN,
                               0, 0, 0.0, 0.0, 0, None),)
mo.ExplicitDynamicsStep(**step_kw)
mo.SmoothStepAmplitude(name='STROKE', timeSpan=STEP, data=((0.0, 0.0), (T_END, 1.0)))
mo.fieldOutputRequests['F-Output-1'].setValues(variables=('S', 'LE', 'PEEQ', 'U', 'STATUS', 'SDEG', 'DMICRT', 'STH'),
                                               numIntervals=N_FIELD)
mo.historyOutputRequests['H-Output-1'].setValues(variables=('ALLKE', 'ALLIE', 'ALLAE', 'ALLWK', 'ALLPD', 'ALLMW',
                                                            'ALLDMD', 'ETOTAL', 'DMASS'), numIntervals=200)
mo.HistoryOutputRequest(name='H-PUNCH', createStepName='STRETCH', variables=('U3', 'RF3'),
                        region=a.sets['RP_PUNCH'], numIntervals=200)
cp = mo.ContactProperty('CP_LUB')
cp.TangentialBehavior(formulation=PENALTY, table=((FRICTION,),), maximumElasticSlip=FRACTION, fraction=0.005)
cp.NormalBehavior(pressureOverclosure=HARD, allowSeparation=ON)
gc = mo.ContactExp(name='GENERAL', createStepName='Initial')
gc.includedPairs.setValuesInStep(stepName='Initial', useAllstar=ON)
gc.contactPropertyAssignments.appendInStep(stepName='Initial', assignments=((GLOBAL, SELF, 'CP_LUB'),))
mo.EncastreBC(name='CLAMP', createStepName='Initial', region=a.sets['CLAMP'])
mo.XsymmBC(name='SYM_X', createStepName='Initial', region=a.sets['SYM_X'])
mo.YsymmBC(name='SYM_Y', createStepName='Initial', region=a.sets['SYM_Y'])
mo.DisplacementBC(name='PUNCH', createStepName='STRETCH', region=a.sets['RP_PUNCH'], u1=0.0, u2=0.0,
                  u3=DEPTH, ur1=0.0, ur2=0.0, ur3=0.0, amplitude='STROKE')

log('blank elements=%d  punch elements=%d  initial yield=%.4g MPa  stroke %.4g mm over %.3g s'
    % (len(blank.elements), len(punch.elements), sy0, DEPTH, T_END))
job = mdb.Job(name=JOB, model=MODEL_NAME, numCpus=CPUS, numDomains=CPUS)
job.writeInput(consistencyChecking=OFF)
mdb.saveAs(pathName=JOB + '.cae')
if SUBMIT:
    job.submit(consistencyChecking=OFF)
    job.waitForCompletion()
    log('done: abaqus python fld_extract.py %s.odb --rp-set RP_PUNCH' % JOB)
