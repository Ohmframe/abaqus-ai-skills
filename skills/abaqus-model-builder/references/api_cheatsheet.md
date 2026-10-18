# Abaqus scripting cheat sheet (kernel, CAE noGUI)

These are the calls `build_from_spec.py` makes, so you can extend the script or write a one-off by hand.
Units are whatever you are consistent in.

```python
from abaqus import *
from abaqusConstants import *
from caeModules import *          # needed for mdb.openStep and friends
import mesh, regionToolset

Mdb()                                           # fresh database
m = mdb.Model(name='Beam'); del mdb.models['Model-1']

# --- part: sketch + extrude
s = m.ConstrainedSketch(name='__p__', sheetSize=2000.0)
s.rectangle(point1=(0.0, 0.0), point2=(1000.0, 100.0))
p = m.Part(name='BEAM', dimensionality=THREE_D, type=DEFORMABLE_BODY)
p.BaseSolidExtrude(sketch=s, depth=50.0)        # shells: p.BaseShell(sketch=s)
# STEP import
g = mdb.openStep(fileName='part.step', scaleFromFile=OFF)
q = m.PartFromGeometryFile(name='IMP', geometryFile=g, combine=True, dimensionality=THREE_D,
                           type=DEFORMABLE_BODY)

# --- partition with a datum plane
d = p.DatumPlaneByPrincipalPlane(principalPlane=YZPLANE, offset=500.0)
p.PartitionCellByDatumPlane(datumPlane=p.datums[d.id], cells=p.cells)

# --- material, section, assignment
mat = m.Material(name='Steel'); mat.Density(table=((7.85e-9,),)); mat.Elastic(table=((210000.0, 0.3),))
mat.Plastic(table=((355.0, 0.0), (450.0, 0.1)))
m.HomogeneousSolidSection(name='SEC', material='Steel', thickness=None)
p.SectionAssignment(region=p.Set(name='ALL', cells=p.cells), sectionName='SEC')

# --- mesh
p.setMeshControls(regions=p.cells, elemShape=HEX, technique=STRUCTURED)
p.setElementType(regions=(p.cells,), elemTypes=(mesh.ElemType(elemCode=C3D8I, elemLibrary=STANDARD),))
p.seedPart(size=10.0, deviationFactor=0.1, minSizeFactor=0.1)
p.seedEdgeByNumber(edges=p.edges.getByBoundingBox(xMin=-1, xMax=1, yMin=-1, yMax=101, zMin=-1, zMax=51),
                   number=8, constraint=FIXED)
p.generateMesh()
chk = p.verifyMeshQuality(criterion=ANALYSIS_CHECKS)   # dict: failedElements, warningElements

# --- assembly, sets, RP + coupling
a = m.rootAssembly; a.DatumCsysByDefault(CARTESIAN)
i = a.Instance(name='BEAM-1', part=p, dependent=ON)
a.translate(instanceList=('BEAM-1',), vector=(0.0, 0.0, 0.0))
a.Set(name='FIX', faces=i.faces.getByBoundingBox(xMin=-1e-6, xMax=1e-6, yMin=-1, yMax=101, zMin=-1, zMax=51))
rp = a.ReferencePoint(point=(1000.0, 50.0, 25.0))
a.Set(name='RP_TIP', referencePoints=(a.referencePoints[rp.id],))
a.Set(name='TIP', faces=i.faces.getByBoundingBox(xMin=999.9, xMax=1000.1, yMin=-1, yMax=101, zMin=-1, zMax=51))
m.Coupling(name='CPL', controlPoint=a.sets['RP_TIP'], surface=a.sets['TIP'], influenceRadius=WHOLE_SURFACE,
           couplingType=KINEMATIC, localCsys=None, u1=ON, u2=ON, u3=ON, ur1=ON, ur2=ON, ur3=ON)

# --- steps
m.StaticStep(name='Load', previous='Initial', nlgeom=OFF)
m.FrequencyStep(name='Modes', previous='Initial', numEigen=10, eigensolver=LANCZOS)
m.ExplicitDynamicsStep(name='Impact', previous='Initial', timePeriod=0.005, nlgeom=ON,
    massScaling=((SEMI_AUTOMATIC, MODEL, AT_BEGINNING, 0.0, 1e-7, BELOW_MIN, 0, 0, 0.0, 0.0, 0, None),))
m.steps['Impact'].Restart(numberIntervals=10, overlay=ON, timeMarks=OFF)
m.HeatTransferStep(name='Steady', previous='Initial', response=STEADY_STATE, amplitude=STEP)

# --- BCs, loads, predefined fields
m.EncastreBC(name='BC_FIX', createStepName='Initial', region=a.sets['FIX'])
m.DisplacementBC(name='BC_U', createStepName='Load', region=a.sets['RP_TIP'], u2=-5.0)
m.ConcentratedForce(name='F', createStepName='Load', region=a.sets['RP_TIP'], cf2=-1000.0)
m.Pressure(name='P', createStepName='Load', region=a.surfaces['TOP'], magnitude=0.1)
m.Gravity(name='G', createStepName='Load', comp2=-9810.0)              # mm/s^2
m.Velocity(name='V0', region=a.sets['IMPACTOR'], field='', distributionType=MAGNITUDE,
           velocity1=0.0, velocity2=-5000.0, velocity3=0.0, omega=0.0)

# --- interactions
m.Tie(name='TIE', main=a.surfaces['M'], secondary=a.surfaces['S'], positionToleranceMethod=COMPUTED,
      adjust=OFF, tieRotations=ON, thickness=ON)                         # 2021-: master=/slave=
ip = m.ContactProperty('FRIC')
ip.NormalBehavior(pressureOverclosure=HARD, allowSeparation=ON)
ip.TangentialBehavior(formulation=PENALTY, table=((0.2,),), maximumElasticSlip=FRACTION, fraction=0.005)
gc = m.ContactExp(name='GC', createStepName='Initial')                   # ContactStd for Standard
gc.includedPairs.setValuesInStep(stepName='Initial', useAllstar=ON)
gc.contactPropertyAssignments.appendInStep(stepName='Initial', assignments=((GLOBAL, SELF, 'FRIC'),))

# --- output, job, save
m.fieldOutputRequests['F-Output-1'].setValues(variables=('S', 'U', 'RF', 'PEEQ'))
m.HistoryOutputRequest(name='H_TIP', createStepName='Load', variables=('U2', 'RF2'), region=a.sets['RP_TIP'])
j = mdb.Job(name='Beam', model='Beam', numCpus=4, numDomains=4)
j.writeInput(consistencyChecking=OFF)
mdb.saveAs(pathName='Beam.cae')
```

## Batch commands

```bash
abaqus cae noGUI=build.py -- args          # build (uses a CAE token)
abaqus job=Beam input=Beam.inp datacheck interactive        # pre-processor only: fast set-up check
abaqus job=Beam input=Beam.inp cpus=4 interactive ask_delete=OFF
abaqus job=Beam input=Beam.inp double=both scratch=/tmp/abq interactive   # long explicit runs
abaqus job=Beam recover                    # continue an explicit run from restart data
abaqus python post.py Beam.odb             # ODB post-processing (no CAE token)
abaqus viewer noGUI=images.py              # off-screen images from an ODB
```

On Windows, call the launcher `abaqus.bat` in the SIMULIA `Commands` folder. It's often not on
PATH. From Git Bash, `cmd //c "abaqus.bat job=..."` works.

## Files a job writes, and what to read

| File | Read it for |
|---|---|
| `.log` | `COMPLETED` or `exited with error`. Licence messages. |
| `.dat` | Pre-processor ERRORs/WARNINGs, model size (`NUMBER OF NODES`), printed results. |
| `.msg` | Increment-by-increment solver messages (Standard): convergence, contact, zero pivots. |
| `.sta` | One line per increment. Standard: attempts (`U` = cutback). Explicit: stable increment, energies, % mass change. |
| `.odb` | Results. Use `abaqus-odb-extract`. |

Everything else (`.com .prt .sim .mdl .stt .res .abq .pac .sel .ipm .lck`) is solver scratch or restart
data. Keep it out of git.
