# -*- coding: utf-8 -*-
"""
scratch_static_check.py - throw-away linear static solve that proves a repaired mesh "holds
together": a copy of one part gets dummy steel-like properties, is clamped at one end and loaded
by gravity. If panels are not really connected, max |U| is huge or the job dies with
zero-pivot / numerical singularity warnings; if they are, the reaction balances the weight.

    abaqus cae noGUI=scratch_static_check.py -- cae:model.cae model:Model-1 part:FE \
        [axis:x] [units:SI_m] [thick:0.002] [cpus:1]

  axis   clamp every node within 1 % of the bounding-box minimum along this axis (x, y or z)
  units  SI_m (m, kg, N, Pa) or SI_mm (mm, t, N, MPa); only sets the dummy properties and g
  thick  shell thickness for shell parts (ignored for solids)

The original model is never touched: everything happens in model "SCRATCH" of an in-memory copy
and the .cae is NOT saved. Job files are written as scratch_check.* in the working directory.

Result (stdout and scratch_check_result.json): nodes/elements, max |U| and where, sum of
RF in the gravity direction vs the weight, warning counts from the .msg.

Python 2.7 and 3.  OhmFrame - https://ohmframe.com - MIT licence.
"""
from __future__ import print_function

import json
import os
import re
import sys

from abaqus import *
from abaqusConstants import *
from caeModules import *
import odbAccess
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


def log(s):
    sys.__stdout__.write(str(s) + '\n')
    sys.__stdout__.flush()


CAE, MODEL, PART = arg('cae'), arg('model', 'Model-1'), arg('part', 'Part-1')
AXIS = 'xyz'.index(arg('axis', 'x').lower())
UNITS = arg('units', 'SI_m')
THICK = arg('thick', 0.002, float)
CPUS = arg('cpus', 1, int)
PROPS = {'SI_m': dict(E=210e9, nu=0.3, rho=7850.0, g=9.81),
         'SI_mm': dict(E=210e3, nu=0.3, rho=7.85e-9, g=9810.0)}[UNITS]
JOB = 'scratch_check'

if CAE:
    openMdb(pathName=CAE)
src = mdb.models[MODEL]
mo = mdb.Model(name='SCRATCH', objectToCopy=src)
# The copy also brings the original BCs, loads, constraints, interactions and output requests.
# They point at assembly sets of instances this script is about to delete, which makes the input
# file reference undefined node sets ("NODE SET ... HAS NOT BEEN DEFINED") and the job dies in the
# pre-processor. Strip everything that refers to the assembly, in dependency order.
for k in list(mo.steps.keys()):
    if k != 'Initial':
        del mo.steps[k]
for repo in ('boundaryConditions', 'loads', 'predefinedFields', 'constraints', 'interactions',
             'fieldOutputRequests', 'historyOutputRequests'):
    r = getattr(mo, repo, None)
    for k in (list(r.keys()) if r is not None else []):
        del r[k]
for k in list(mo.rootAssembly.instances.keys()):
    del mo.rootAssembly.instances[k]
for repo in (mo.rootAssembly.surfaces, mo.rootAssembly.sets):
    for k in list(repo.keys()):
        del repo[k]
p = mo.parts[PART]

shell = False
for el in p.elements:
    shell = str(el.type).startswith(('S', 'M3D', 'STRI'))
    break
mat = mo.Material(name='DUMMY_STEEL')
mat.Elastic(table=((PROPS['E'], PROPS['nu']),))
mat.Density(table=((PROPS['rho'],),))
if shell:
    mo.HomogeneousShellSection(name='DUMMY_SEC', material='DUMMY_STEEL', thickness=THICK)
else:
    mo.HomogeneousSolidSection(name='DUMMY_SEC', material='DUMMY_STEEL')
region = p.Set(name='ALL_E_SCRATCH', elements=p.elements)
for i in range(len(p.sectionAssignments) - 1, -1, -1):   # drop original assignments (copy only)
    del p.sectionAssignments[i]
p.SectionAssignment(region=region, sectionName='DUMMY_SEC')

a = mo.rootAssembly
inst = a.Instance(name='I', part=p, dependent=ON)
cs = [n.coordinates[AXIS] for n in inst.nodes]
lo, hi = min(cs), max(cs)
tol = 0.01 * (hi - lo)
clamp = [n.label for n in inst.nodes if n.coordinates[AXIS] <= lo + tol]
a.Set(name='CLAMP', nodes=inst.nodes.sequenceFromLabels(clamp))
mo.StaticStep(name='LOAD', previous='Initial', nlgeom=OFF)
mo.EncastreBC(name='CLAMP', createStepName='Initial', region=a.sets['CLAMP'])
gdir = (AXIS + 1) % 3                     # gravity perpendicular to the clamp axis
comps = [0.0, 0.0, 0.0]
comps[gdir] = -PROPS['g']
mo.Gravity(name='G', createStepName='LOAD', comp1=comps[0], comp2=comps[1], comp3=comps[2])
mo.FieldOutputRequest(name='F-Output-1', createStepName='LOAD', variables=('U', 'RF', 'S'))
log('scratch model: %s elements=%d nodes=%d clamped nodes=%d gravity on axis %s'
    % ('shell' if shell else 'solid', len(inst.elements), len(inst.nodes), len(clamp), 'xyz'[gdir]))
job = mdb.Job(name=JOB, model='SCRATCH', numCpus=CPUS, numDomains=CPUS)
job.submit(consistencyChecking=OFF)
job.waitForCompletion()


def job_status():
    """job.status is None for a batch job in some releases; the .log is authoritative."""
    if job.status is not None:
        return str(job.status)
    try:
        tail = open(JOB + '.log').read()
    except IOError:
        return 'UNKNOWN (no .log)'
    if 'exited with errors' in tail or 'Abaqus Error' in tail:
        return 'ABORTED (see %s.dat)' % JOB
    return 'COMPLETED' if 'COMPLETED' in tail else 'UNKNOWN'


status = job_status()
log('job %s finished with status %s' % (JOB, status))

res = dict(model=MODEL, part=PART, shell=shell, elements=len(inst.elements), nodes=len(inst.nodes),
           clamped_nodes=len(clamp), job_status=status)
try:
    msg = open(JOB + '.msg').read()
    res['zero_pivot'] = len(re.findall(r'ZERO PIVOT', msg))
    res['singularity'] = len(re.findall(r'NUMERICAL SINGULARITY', msg))
except IOError:
    res['zero_pivot'] = res['singularity'] = None
try:
    odb = odbAccess.openOdb(JOB + '.odb', readOnly=True)
    fr = odb.steps['LOAD'].frames[-1]
    um, ul = 0.0, None
    for v in fr.fieldOutputs['U'].values:
        if v.magnitude > um:
            um, ul = v.magnitude, v.nodeLabel
    rf = sum(v.data[gdir] for v in fr.fieldOutputs['RF'].values)
    smax = max(v.mises for v in fr.fieldOutputs['S'].values)
    odb.close()
    span = hi - lo
    res.update(max_U=um, max_U_node=ul, sum_RF_gravity_dir=rf, max_mises=smax, span=span,
               U_over_span=um / span if span else None)
except Exception as exc:
    res['odb_error'] = str(exc)
    log('ERROR: could not read %s.odb (%s). Read %s.dat / %s.log before trusting anything below.'
        % (JOB, exc, JOB, JOB))
json.dump(res, open(JOB + '_result.json', 'w'), indent=2)
for k in sorted(res):
    log('  %-20s %s' % (k, res[k]))
log('Interpretation: sum_RF should equal the weight (+ sign, opposite gravity). '
    'U/span far above ~1e-2, or ZERO PIVOT / NUMERICAL SINGULARITY warnings => parts not connected.')
