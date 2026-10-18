# -*- coding: utf-8 -*-
"""
build_layered_slab.py - Abaqus heat-transfer template for a multi-layer wall/roof/floor build-up:
steady-state (U-value) or transient (daily cycle) conduction through layers, with film
conditions on both faces. Parameters in a JSON file or the DEFAULT_SPEC block below.

    abaqus cae noGUI=build_layered_slab.py                     # DEFAULT_SPEC (textbook 3-layer wall)
    abaqus cae noGUI=build_layered_slab.py -- slab.json        # your layers
    abaqus cae noGUI=build_layered_slab.py -- slab.json submit
    then:  abaqus python u_value.py slab.odb --set ALL_LAYERS --dT 20

Units: SI (m, s, kg, W, degC). k in W/(m K), rho kg/m^3, cp J/(kg K), h W/(m^2 K).

Geometry: a block of the total thickness along X and WIDTH x WIDTH in Y and Z (1D through the
thickness: the side faces are adiabatic by default). Each layer is a partitioned cell with its own
material and section; element sets L_<name>, surfaces INSIDE (x = 0) and OUTSIDE (x = total).
Film coefficients: h = 1/Rs (default Rsi = 0.13, Rse = 0.04 m^2K/W, the usual design values).

JSON keys (all optional except layers):
  {"name": "slab", "layers": [{"name": "BRICK", "t": 0.1, "k": 0.77, "rho": 1700, "cp": 800}, ...],
   "width": 0.1, "Ti": 20.0, "Te": 0.0, "Rsi": 0.13, "Rse": 0.04, "seed": 0.01,
   "transient": {"period": 86400, "dt0": 60, "dtmax": 600, "deltmx": 2.0,
                 "Te_table": [[0, 0.0], [43200, 10.0], [86400, 0.0]], "T0": 10.0}}
Without "transient" a steady-state step is created.

Python 2.7 and 3.  OhmFrame - https://ohmframe.com - MIT licence.
"""
from __future__ import print_function

import json
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

DEFAULT_SPEC = {
    "name": "slab",
    "layers": [
        {"name": "BRICK", "t": 0.100, "k": 0.77, "rho": 1700.0, "cp": 800.0},
        {"name": "INSULATION", "t": 0.100, "k": 0.035, "rho": 30.0, "cp": 1030.0},
        {"name": "BLOCK", "t": 0.100, "k": 0.50, "rho": 1400.0, "cp": 1000.0},
    ],
    "width": 0.1, "Ti": 20.0, "Te": 0.0, "Rsi": 0.13, "Rse": 0.04, "seed": 0.01,
}


def log(s):
    sys.__stdout__.write(str(s) + '\n')
    sys.__stdout__.flush()


def to_str(o):
    """json gives unicode on Python 2; Abaqus names must be str."""
    if isinstance(o, dict):
        return dict((to_str(k), to_str(v)) for k, v in o.items())
    if isinstance(o, list):
        return [to_str(v) for v in o]
    try:
        if isinstance(o, unicode):        # noqa: F821  (Python 2 only)
            return str(o)
    except NameError:
        pass
    return o


# Abaqus strips the '--' separator before the script sees sys.argv (checked on 2023), so never
# rely on it being there: scan the whole command line instead. Without this the script silently
# fell back to DEFAULT_SPEC and ignored the JSON file.
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
spec = dict(DEFAULT_SPEC)
for a in args:
    if a.lower().endswith('.json'):
        spec.update(to_str(json.load(open(a))))
SUBMIT = 'submit' in args
layers = spec['layers']
W = float(spec['width'])
total = sum(float(L['t']) for L in layers)
NAME = spec['name']

mo = mdb.Model(name=NAME, modelType=STANDARD_EXPLICIT)
if 'Model-1' in mdb.models.keys():
    del mdb.models['Model-1']
mo.setValues(absoluteZero=-273.15, stefanBoltzmann=5.670374e-08)   # needed only if radiation is added

sk = mo.ConstrainedSketch(name='prof', sheetSize=4 * max(total, W))
sk.rectangle(point1=(0.0, 0.0), point2=(total, W))
p = mo.Part(name='SLAB', dimensionality=THREE_D, type=DEFORMABLE_BODY)
p.BaseSolidExtrude(sketch=sk, depth=W)
x = 0.0
for L in layers[:-1]:
    x += float(L['t'])
    dp = p.DatumPlaneByPrincipalPlane(principalPlane=YZPLANE, offset=x)
    p.PartitionCellByDatumPlane(datumPlane=p.datums[dp.id], cells=p.cells)

eps = 1e-6
x = 0.0
all_cells = None
for L in layers:
    nm = L['name'].upper()
    t = float(L['t'])
    mat = mo.Material(name='M_' + nm)
    mat.Conductivity(table=((float(L['k']),),))
    mat.Density(table=((float(L.get('rho', 1000.0)),),))
    mat.SpecificHeat(table=((float(L.get('cp', 1000.0)),),))
    mo.HomogeneousSolidSection(name='S_' + nm, material='M_' + nm)
    cells = p.cells.getByBoundingBox(x - eps, -eps, -eps, x + t + eps, W + eps, W + eps)
    if len(cells) != 1:
        raise RuntimeError('layer %s: expected 1 cell, found %d' % (nm, len(cells)))
    p.SectionAssignment(region=p.Set(name='L_' + nm, cells=cells), sectionName='S_' + nm)
    # at least 2 elements through each layer
    ex = p.edges.getByBoundingBox(x - eps, -eps, -eps, x + t + eps, W + eps, W + eps)
    thick_edges = [e for e in ex if abs(abs(p.vertices[e.getVertices()[0]].pointOn[0][0] -
                                            p.vertices[e.getVertices()[1]].pointOn[0][0]) - t) < 1e-9]
    n = max(2, int(round(t / float(spec['seed']))))
    p.seedEdgeByNumber(edges=p.edges.findAt(*[(e.pointOn[0],) for e in thick_edges]), number=n, constraint=FIXED)
    x += t
p.Set(name='ALL_LAYERS', cells=p.cells)
lateral = [e for e in p.edges if abs(p.vertices[e.getVertices()[0]].pointOn[0][0] -
                                     p.vertices[e.getVertices()[1]].pointOn[0][0]) < 1e-9]
p.seedEdgeByNumber(edges=p.edges.findAt(*[(e.pointOn[0],) for e in lateral]), number=1, constraint=FIXED)
p.setMeshControls(regions=p.cells, elemShape=HEX, technique=STRUCTURED)
p.setElementType(regions=(p.cells,), elemTypes=(mesh.ElemType(elemCode=DC3D8, elemLibrary=STANDARD),))
p.generateMesh()

a = mo.rootAssembly
a.DatumCsysByDefault(CARTESIAN)
inst = a.Instance(name='SLAB-1', part=p, dependent=ON)
a.Surface(name='INSIDE', side1Faces=inst.faces.getByBoundingBox(-eps, -eps, -eps, eps, W + eps, W + eps))
a.Surface(name='OUTSIDE', side1Faces=inst.faces.getByBoundingBox(total - eps, -eps, -eps, total + eps, W + eps, W + eps))

Ti, Te = float(spec['Ti']), float(spec['Te'])
hi, he = 1.0 / float(spec['Rsi']), 1.0 / float(spec['Rse'])
tr = spec.get('transient')
if tr:
    mo.HeatTransferStep(name='HEAT', previous='Initial', response=TRANSIENT, timePeriod=float(tr['period']),
                        initialInc=float(tr.get('dt0', 60.0)), minInc=1e-3, maxInc=float(tr.get('dtmax', 600.0)),
                        maxNumInc=100000, deltmx=float(tr.get('deltmx', 2.0)))
    tab = tuple((float(t_), float(v)) for t_, v in tr['Te_table'])
    mo.TabularAmplitude(name='TE_AMP', timeSpan=STEP, smooth=SOLVER_DEFAULT, data=tab)
    mo.Temperature(name='T0', createStepName='Initial', region=a.instances['SLAB-1'].sets['ALL_LAYERS'],
                   magnitudes=(float(tr.get('T0', Ti)),))
    mo.FilmCondition(name='FILM_OUT', createStepName='HEAT', surface=a.surfaces['OUTSIDE'],
                     definition=EMBEDDED_COEFF, filmCoeff=he, sinkTemperature=1.0, sinkAmplitude='TE_AMP')
else:
    mo.HeatTransferStep(name='HEAT', previous='Initial', response=STEADY_STATE, amplitude=RAMP)
    mo.FilmCondition(name='FILM_OUT', createStepName='HEAT', surface=a.surfaces['OUTSIDE'],
                     definition=EMBEDDED_COEFF, filmCoeff=he, sinkTemperature=Te)
mo.FilmCondition(name='FILM_IN', createStepName='HEAT', surface=a.surfaces['INSIDE'],
                 definition=EMBEDDED_COEFF, filmCoeff=hi, sinkTemperature=Ti)
mo.FieldOutputRequest(name='F-HEAT', createStepName='HEAT', variables=('NT', 'HFL', 'EVOL', 'RFL'))

R = float(spec['Rsi']) + sum(float(L['t']) / float(L['k']) for L in layers) + float(spec['Rse'])
U = 1.0 / R
log('layers=%d total=%.4g m elements=%d  hand calc: R=%.5g m2K/W  U=%.5g W/m2K  q=%.5g W/m2 (dT=%.4g)'
    % (len(layers), total, len(p.elements), R, U, U * (Ti - Te), Ti - Te))
json.dump(dict(R_total=R, U=U, q=U * (Ti - Te), layers=layers, Rsi=spec['Rsi'], Rse=spec['Rse']),
          open(NAME + '_handcalc.json', 'w'), indent=2)
job = mdb.Job(name=NAME, model=NAME)
job.writeInput(consistencyChecking=OFF)
mdb.saveAs(pathName=NAME + '.cae')
if SUBMIT:
    job.submit(consistencyChecking=OFF)
    job.waitForCompletion()
    log('done: abaqus python u_value.py %s.odb --set ALL_LAYERS --dT %.4g' % (NAME, Ti - Te))
