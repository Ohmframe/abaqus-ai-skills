# -*- coding: utf-8 -*-
"""
build_from_spec.py - build a native Abaqus/CAE model (.cae + .inp) from a JSON spec.

    abaqus cae noGUI=build_from_spec.py -- my_model.json
    abaqus cae noGUI=build_from_spec.py -- my_model.json --submit      (also run the job inside CAE)

The spec describes parts, materials, sections, assembly, sets, steps, BCs, loads,
interactions, mesh, outputs and job. See ../references/spec_schema.md and
../examples/cantilever_beam.json.

What the script guarantees before it saves anything:
  * every set/surface selection is non-empty (an empty bounding-box pick aborts the build)
  * every part that has a mesh block actually meshed (0 elements aborts the build)
  * a manifest <job>_model.json is written next to the .cae (counts, sets, steps, units)

Runs under Abaqus Python 2.7 (<= 2023) and Python 3 (2024+). No f-strings on purpose.

OhmFrame - https://ohmframe.com - MIT licence. Verify every result yourself.
"""
from __future__ import print_function

import json
import math
import os
import sys

from abaqus import *                     # noqa: F401,F403  (mdb, session, ...)
from abaqusConstants import *            # noqa: F401,F403
from caeModules import *                 # noqa: F401,F403  (needed before mdb.openStep)
import abaqusConstants
import mesh
import regionToolset

# 'from abaqus import *' shadows some Python built-ins (sum, min, max, abs, round): restore them.
try:
    import builtins as _bi               # Python 3 (Abaqus 2024+)
except ImportError:                      # Python 2.7 (Abaqus 2023 and older)
    import __builtin__ as _bi
sum, min, max, abs, round = _bi.sum, _bi.min, _bi.max, _bi.abs, _bi.round

try:
    _TEXT = (str, unicode)               # noqa: F821  (Python 2)
except NameError:
    _TEXT = (str,)


# ----------------------------------------------------------------------------- utilities
def log(*args):
    """Under 'cae noGUI=' plain print can be swallowed; write to the real stdout."""
    sys.__stdout__.write(' '.join(str(a) for a in args) + '\n')
    sys.__stdout__.flush()


def to_str(o):
    """json returns unicode in Python 2; the Abaqus API wants str for names."""
    if isinstance(o, dict):
        return dict((to_str(k), to_str(v)) for k, v in o.items())
    if isinstance(o, list):
        return [to_str(i) for i in o]
    if isinstance(o, _TEXT) and not isinstance(o, str):
        return str(o)
    return o


def const(name):
    """'HEX' -> abaqusConstants.HEX, with a clear error for typos."""
    if not isinstance(name, str):
        return name
    try:
        return getattr(abaqusConstants, name.upper())
    except AttributeError:
        raise ValueError('Unknown Abaqus constant "%s" in spec' % name)


def bbox_kw(b, tol=0.0):
    return dict(xMin=b[0] - tol, yMin=b[1] - tol, zMin=b[2] - tol,
                xMax=b[3] + tol, yMax=b[4] + tol, zMax=b[5] + tol)


def parse_args(argv):
    args = argv[argv.index('--') + 1:] if '--' in argv else argv[1:]
    spec = [a for a in args if a.lower().endswith('.json')]
    if not spec:
        raise SystemExit('usage: abaqus cae noGUI=build_from_spec.py -- spec.json [--submit]')
    return spec[0], ('--submit' in args)


# ----------------------------------------------------------------------------- unit sanity
DENSITY_RANGE = {          # rough plausible solid densities in each unit system
    'mm-N-tonne-s': (1.0e-10, 3.0e-8),
    'm-N-kg-s': (1.0, 3.0e4),
    'in-lbf-lbfs2in-s': (1.0e-6, 3.0e-3),
}


def check_units(spec):
    u = spec.get('units', '')
    rng = None
    for key, r in DENSITY_RANGE.items():
        if u.startswith(key):
            rng = r
    if rng is None:
        log('NOTE: units "%s" not recognised, density sanity check skipped' % u)
        return
    for mat in spec.get('materials', []):
        rho = mat.get('density')
        if rho is not None and not (rng[0] <= rho <= rng[1]):
            log('WARNING: material %s density %g is outside the usual range %s for units %s. '
                'Check the unit system before trusting dynamics, gravity or mass.'
                % (mat['name'], rho, rng, u))


# ----------------------------------------------------------------------------- parts
def make_sketch(m, name, size):
    return m.ConstrainedSketch(name=name, sheetSize=size)


def build_part(m, ps):
    name, kind = ps['name'], ps['type']
    shell = ps.get('shell', False)
    if kind == 'step':
        g = mdb.openStep(fileName=ps['file'], scaleFromFile=OFF)
        p = m.PartFromGeometryFile(name=name, geometryFile=g, combine=ps.get('combine', True),
                                   dimensionality=THREE_D, type=DEFORMABLE_BODY)
        if not p.geometryValidity:
            log('WARNING: %s imported with invalid geometry. Run abaqus-mesh-doctor before meshing.' % name)
        return p
    sk = make_sketch(m, '__%s__' % name, ps.get('sheet_size', 2000.0))
    if kind == 'box':
        dx, dy, dz = ps['size']
        sk.rectangle(point1=(0.0, 0.0), point2=(dx, dy))
        depth = dz
    elif kind == 'rect_shell':
        dx, dy = ps['size'][:2]
        sk.rectangle(point1=(0.0, 0.0), point2=(dx, dy))
        shell, depth = True, None
    elif kind == 'plate_with_hole':
        dx, dy = ps['size'][:2]
        cx, cy = ps.get('hole_center', [dx / 2.0, dy / 2.0])
        r = ps['hole_radius']
        sk.rectangle(point1=(0.0, 0.0), point2=(dx, dy))
        sk.CircleByCenterPerimeter(center=(cx, cy), point1=(cx + r, cy))
        depth = ps.get('thickness')
    elif kind == 'cylinder':
        sk.CircleByCenterPerimeter(center=(0.0, 0.0), point1=(ps['radius'], 0.0))
        depth = ps['length']
    elif kind == 'polygon':
        pts = [tuple(q) for q in ps['points']]
        for i in range(len(pts)):
            sk.Line(point1=pts[i], point2=pts[(i + 1) % len(pts)])
        depth = ps.get('thickness')
    else:
        raise ValueError('part %s: unknown type %s' % (name, kind))
    p = m.Part(name=name, dimensionality=THREE_D, type=DEFORMABLE_BODY)
    if shell or depth is None:
        p.BaseShell(sketch=sk)
    else:
        p.BaseSolidExtrude(sketch=sk, depth=depth)
    del m.sketches['__%s__' % name]
    return p


PLANES = {'XY': 'XYPLANE', 'YZ': 'YZPLANE', 'XZ': 'XZPLANE'}


def partition_part(p, ops):
    for op in ops or []:
        if op['type'] == 'principal_plane':
            d = p.DatumPlaneByPrincipalPlane(principalPlane=const(PLANES[op['plane']]),
                                             offset=op.get('offset', 0.0))
        elif op['type'] == 'three_points':
            a, b, c = [tuple(q) for q in op['points']]
            d = p.DatumPlaneByThreePoints(point1=a, point2=b, point3=c)
        else:
            raise ValueError('unknown partition type %s' % op['type'])
        dp = p.datums[d.id]
        if len(p.cells):
            p.PartitionCellByDatumPlane(datumPlane=dp, cells=p.cells)
        else:
            p.PartitionFaceByDatumPlane(datumPlane=dp, faces=p.faces)


# ----------------------------------------------------------------------------- materials, sections
def build_material(m, ms):
    mat = m.Material(name=ms['name'])
    if 'density' in ms:
        mat.Density(table=((ms['density'],),))
    if 'elastic' in ms:
        mat.Elastic(table=(tuple(ms['elastic']),))
    if 'plastic' in ms:                       # rows of (true stress, plastic strain), first strain 0
        mat.Plastic(table=tuple(tuple(r) for r in ms['plastic']))
    if 'conductivity' in ms:
        mat.Conductivity(table=((ms['conductivity'],),))
    if 'specific_heat' in ms:
        mat.SpecificHeat(table=((ms['specific_heat'],),))
    if 'expansion' in ms:
        mat.Expansion(table=((ms['expansion'],),))
    return mat


def build_section(m, ss):
    kind = ss.get('type', 'solid')
    if kind == 'solid':
        m.HomogeneousSolidSection(name=ss['name'], material=ss['material'], thickness=None)
    elif kind == 'shell':
        m.HomogeneousShellSection(name=ss['name'], material=ss['material'], thickness=ss['thickness'],
                                  integrationRule=SIMPSON, numIntPts=ss.get('int_points', 5))
    else:
        raise ValueError('unknown section type %s' % kind)


def assign_section(p, sa):
    if len(p.cells):
        region = p.Set(name=sa.get('set', 'ALL'), cells=p.cells)
    else:
        region = p.Set(name=sa.get('set', 'ALL'), faces=p.faces)
    p.SectionAssignment(region=region, sectionName=sa['section'], offset=0.0,
                        offsetType=MIDDLE_SURFACE, offsetField='', thicknessAssignment=FROM_SECTION)


# ----------------------------------------------------------------------------- mesh
def mesh_part(p, ms):
    regions = p.cells if len(p.cells) else p.faces
    if 'elem_shape' in ms:
        kw = dict(regions=regions, elemShape=const(ms['elem_shape']))
        if 'technique' in ms:
            kw['technique'] = const(ms['technique'])
        try:
            p.setMeshControls(**kw)
        except Exception as exc:          # e.g. STRUCTURED not possible on an unpartitioned cell
            log('WARNING: %s mesh controls %s rejected (%s); falling back to SWEEP/FREE'
                % (p.name, ms.get('technique'), exc))
            if len(p.cells):
                try:
                    p.setMeshControls(regions=regions, elemShape=HEX, technique=SWEEP)
                except Exception:
                    p.setMeshControls(regions=regions, elemShape=TET, technique=FREE)
    lib = const(ms.get('library', 'STANDARD'))
    codes = ms.get('elem_codes', [])
    if codes:
        types = []
        for c in codes:
            kw = dict(elemCode=const(c), elemLibrary=lib)
            if ms.get('hourglass'):
                kw['hourglassControl'] = const(ms['hourglass'])
            types.append(mesh.ElemType(**kw))
        p.setElementType(regions=(regions,), elemTypes=tuple(types))
    p.seedPart(size=ms['seed'], deviationFactor=ms.get('deviation_factor', 0.1),
               minSizeFactor=ms.get('min_size_factor', 0.1))
    for es in ms.get('edge_seeds', []):
        edges = p.edges.getByBoundingBox(**bbox_kw(es['bbox'], 1e-6))
        if not len(edges):
            raise ValueError('part %s: edge seed bbox %s selects no edges' % (p.name, es['bbox']))
        if 'number' in es:
            p.seedEdgeByNumber(edges=edges, number=es['number'], constraint=FIXED)
        else:
            p.seedEdgeBySize(edges=edges, size=es['size'], deviationFactor=0.1, constraint=FINER)
    p.generateMesh()
    if len(p.elements) == 0:
        raise RuntimeError('part %s did not mesh (0 elements). Partition it or change the technique.'
                           % p.name)
    q = p.verifyMeshQuality(criterion=ANALYSIS_CHECKS)
    log('  mesh %-14s nodes %7d  elements %7d  analysis-check errors %d warnings %d'
        % (p.name, len(p.nodes), len(p.elements), len(q['failedElements']), len(q['warningElements'])))
    return dict(nodes=len(p.nodes), elements=len(p.elements),
                check_errors=len(q['failedElements']), check_warnings=len(q['warningElements']))


# ----------------------------------------------------------------------------- assembly, sets
def build_instances(m, specs):
    a = m.rootAssembly
    a.DatumCsysByDefault(CARTESIAN)
    for s in specs:
        a.Instance(name=s['name'], part=m.parts[s['part']], dependent=ON)
        if 'rotate' in s:
            r = s['rotate']
            a.rotate(instanceList=(s['name'],), axisPoint=tuple(r.get('axis_point', (0.0, 0.0, 0.0))),
                     axisDirection=tuple(r['axis_dir']), angle=r['angle'])
        if 'translate' in s:
            a.translate(instanceList=(s['name'],), vector=tuple(s['translate']))
    return a


def select(a, ss):
    inst = a.instances[ss['instance']]
    kind = ss.get('kind', 'faces')
    repo = getattr(inst, kind)
    seq = repo.getByBoundingBox(**bbox_kw(ss['bbox'], ss.get('tol', 1e-6)))
    if not len(seq):
        raise ValueError('selection "%s" (%s of %s in bbox %s) is EMPTY. Fix the bbox before going on.'
                         % (ss['name'], kind, ss['instance'], ss['bbox']))
    return kind, seq


def build_sets(m, a, spec):
    sizes = {}
    for rp in spec.get('reference_points', []):
        f = a.ReferencePoint(point=tuple(rp['point']))
        a.Set(name=rp['name'], referencePoints=(a.referencePoints[f.id],))
        sizes[rp['name']] = 1
    for ss in spec.get('sets', []):
        kind, seq = select(a, ss)
        a.Set(name=ss['name'], **{kind: seq})
        sizes[ss['name']] = len(seq)
    for ss in spec.get('surfaces', []):
        kind, seq = select(a, dict(ss, kind='faces'))
        side = ss.get('side', 'side1')
        key = {'side1': 'side1Faces', 'side2': 'side2Faces', 'both': 'side12Faces'}[side]
        a.Surface(name=ss['name'], **{key: seq})
        sizes[ss['name']] = len(seq)
    for c in spec.get('couplings', []):
        region = a.surfaces[c['surface']] if c['surface'] in a.surfaces.keys() else a.sets[c['surface']]
        m.Coupling(name=c['name'], controlPoint=a.sets[c['control']], surface=region,
                   influenceRadius=WHOLE_SURFACE, couplingType=const(c.get('type', 'KINEMATIC')),
                   localCsys=None, u1=ON, u2=ON, u3=ON, ur1=ON, ur2=ON, ur3=ON)
    for k, v in sorted(sizes.items()):
        log('  set/surface %-20s %d entities' % (k, v))
    return sizes


def region_of(a, name):
    if name in a.surfaces.keys():
        return a.surfaces[name]
    if name in a.sets.keys():
        return a.sets[name]
    raise KeyError('no assembly set or surface named %s' % name)


# ----------------------------------------------------------------------------- steps
def build_steps(m, steps):
    prev = 'Initial'
    for s in steps:
        t, n = s['type'], s['name']
        if t == 'static':
            kw = dict(name=n, previous=prev, nlgeom=ON if s.get('nlgeom') else OFF,
                      timePeriod=s.get('time_period', 1.0), initialInc=s.get('initial_inc', 0.1),
                      maxInc=s.get('max_inc', 1.0), minInc=s.get('min_inc', 1e-8),
                      maxNumInc=s.get('max_num_inc', 1000))
            if s.get('stabilize'):
                kw.update(stabilizationMethod=DISSIPATED_ENERGY_FRACTION,
                          stabilizationMagnitude=s['stabilize'], continueDampingFactors=False,
                          adaptiveDampingRatio=0.05)
            m.StaticStep(**kw)
        elif t == 'frequency':
            m.FrequencyStep(name=n, previous=prev, numEigen=s.get('num_eigen', 10), eigensolver=LANCZOS)
        elif t == 'explicit':
            kw = dict(name=n, previous=prev, timePeriod=s['time_period'], nlgeom=ON)
            if s.get('mass_scaling_dt'):
                # semi-automatic: only elements whose stable increment is below the target are scaled
                kw['massScaling'] = ((SEMI_AUTOMATIC, MODEL, AT_BEGINNING, 0.0, s['mass_scaling_dt'],
                                      BELOW_MIN, 0, 0, 0.0, 0.0, 0, None),)
            m.ExplicitDynamicsStep(**kw)
            if s.get('restart_intervals'):
                m.steps[n].Restart(numberIntervals=s['restart_intervals'], overlay=ON, timeMarks=OFF)
        elif t == 'heat_steady':
            m.HeatTransferStep(name=n, previous=prev, response=STEADY_STATE, amplitude=STEP)
        elif t == 'heat_transient':
            m.HeatTransferStep(name=n, previous=prev, response=TRANSIENT, amplitude=STEP,
                               timePeriod=s['time_period'], initialInc=s.get('initial_inc', 1.0),
                               minInc=s.get('min_inc', 1e-5), maxInc=s.get('max_inc', s['time_period']),
                               deltmx=s.get('deltmx', 5.0), maxNumInc=s.get('max_num_inc', 100000))
        else:
            raise ValueError('unknown step type %s' % t)
        prev = n


# ----------------------------------------------------------------------------- BCs, loads, interactions
DOF = ('u1', 'u2', 'u3', 'ur1', 'ur2', 'ur3')


def build_bcs(m, a, bcs):
    for b in bcs:
        t, n, st = b['type'], b['name'], b.get('step', 'Initial')
        reg = region_of(a, b['set'])
        if t == 'encastre':
            m.EncastreBC(name=n, createStepName=st, region=reg)
        elif t == 'pinned':
            m.PinnedBC(name=n, createStepName=st, region=reg)
        elif t in ('xsymm', 'ysymm', 'zsymm'):
            getattr(m, t[0].upper() + 'symmBC')(name=n, createStepName=st, region=reg)
        elif t in ('displacement', 'velocity'):
            kw = {}
            for d in DOF:
                if d in b:
                    v = b[d]
                    kw[d if t == 'displacement' else d.replace('u', 'v')] = SET if st == 'Initial' else v
            if 'amplitude' in b:
                kw['amplitude'] = b['amplitude']
            if t == 'displacement':
                m.DisplacementBC(name=n, createStepName=st, region=reg, **kw)
            else:
                m.VelocityBC(name=n, createStepName=st, region=reg, **kw)
        elif t == 'temperature':
            m.TemperatureBC(name=n, createStepName=st, region=reg, magnitude=b['magnitude'])
        else:
            raise ValueError('unknown BC type %s' % t)


def build_amplitudes(m, amps):
    for am in amps or []:
        if am['type'] == 'smooth_step':
            m.SmoothStepAmplitude(name=am['name'], timeSpan=STEP,
                                  data=tuple(tuple(r) for r in am['data']))
        else:
            m.TabularAmplitude(name=am['name'], timeSpan=STEP, smooth=SOLVER_DEFAULT,
                               data=tuple(tuple(r) for r in am['data']))


def build_loads(m, a, loads):
    for ld in loads:
        t, n, st = ld['type'], ld['name'], ld['step']
        amp = {'amplitude': ld['amplitude']} if 'amplitude' in ld else {}
        if t == 'concentrated_force':
            kw = dict((k, ld[k]) for k in ('cf1', 'cf2', 'cf3') if k in ld)
            kw.update(amp)
            m.ConcentratedForce(name=n, createStepName=st, region=region_of(a, ld['set']), **kw)
        elif t == 'pressure':
            m.Pressure(name=n, createStepName=st, region=a.surfaces[ld['surface']],
                       magnitude=ld['magnitude'], distributionType=UNIFORM, **amp)
        elif t == 'gravity':
            g = ld['vector']
            m.Gravity(name=n, createStepName=st, comp1=g[0], comp2=g[1], comp3=g[2], **amp)
        elif t == 'surface_heat_flux':
            m.SurfaceHeatFlux(name=n, createStepName=st, region=a.surfaces[ld['surface']],
                              magnitude=ld['magnitude'], **amp)
        else:
            raise ValueError('unknown load type %s' % t)


def build_predefined(m, a, fields):
    for f in fields or []:
        if f['type'] == 'velocity':
            v = f['vector']
            m.Velocity(name=f['name'], region=a.sets[f['set']], field='', distributionType=MAGNITUDE,
                       velocity1=v[0], velocity2=v[1], velocity3=v[2], omega=0.0)
        elif f['type'] == 'temperature':
            m.Temperature(name=f['name'], createStepName='Initial', region=a.sets[f['set']],
                          distributionType=UNIFORM, magnitudes=(f['magnitude'],))


def tie(m, name, main, secondary, **kw):
    """Abaqus 2022+ uses main/secondary; 2021 and older use master/slave."""
    try:
        return m.Tie(name=name, main=main, secondary=secondary, **kw)
    except TypeError:
        return m.Tie(name=name, master=main, slave=secondary, **kw)


def contact_property(m, name, friction):
    ip = m.ContactProperty(name)
    ip.NormalBehavior(pressureOverclosure=HARD, allowSeparation=ON, constraintEnforcementMethod=DEFAULT)
    if friction:
        ip.TangentialBehavior(formulation=PENALTY, table=((friction,),),
                              maximumElasticSlip=FRACTION, fraction=0.005)
    else:
        ip.TangentialBehavior(formulation=FRICTIONLESS)
    return name


def build_interactions(m, a, inters, first_step):
    for it in inters or []:
        t = it['type']
        if t == 'tie':
            kw = dict(positionToleranceMethod=COMPUTED, adjust=ON if it.get('adjust', False) else OFF,
                      tieRotations=ON, thickness=ON)
            if 'position_tolerance' in it:
                kw.update(positionToleranceMethod=SPECIFIED, positionTolerance=it['position_tolerance'])
            tie(m, it['name'], region_of(a, it['main']), region_of(a, it['secondary']), **kw)
        elif t in ('general_contact', 'general_contact_explicit'):
            prop = contact_property(m, it['name'] + '_PROP', it.get('friction', 0.0))
            if t == 'general_contact':
                gc = m.ContactStd(name=it['name'], createStepName='Initial')
            else:
                gc = m.ContactExp(name=it['name'], createStepName='Initial')
            pairs = it.get('pairs')
            if pairs:
                gc.includedPairs.setValuesInStep(stepName='Initial', useAllstar=OFF, addPairs=tuple(
                    (a.surfaces[p0], a.surfaces[p1]) for p0, p1 in pairs))
            else:
                gc.includedPairs.setValuesInStep(stepName='Initial', useAllstar=ON)
            gc.contactPropertyAssignments.appendInStep(stepName='Initial', assignments=((GLOBAL, SELF, prop),))
        elif t == 'film':
            m.FilmCondition(name=it['name'], createStepName=it.get('step', first_step),
                            surface=a.surfaces[it['surface']], definition=EMBEDDED_COEFF,
                            filmCoeff=it['film_coeff'], sinkTemperature=it['sink_temperature'])
        else:
            raise ValueError('unknown interaction type %s' % t)


# ----------------------------------------------------------------------------- outputs, job
def build_outputs(m, a, out, steps):
    first = steps[0]['name']
    fo = out.get('field')
    if fo:
        kw = dict(variables=tuple(fo['variables']))
        if 'num_intervals' in fo:
            kw['numIntervals'] = fo['num_intervals']
        if 'F-Output-1' in m.fieldOutputRequests.keys():
            m.fieldOutputRequests['F-Output-1'].setValues(**kw)
        else:
            m.FieldOutputRequest(name='F-Output-1', createStepName=first, **kw)
    if out.get('energies'):
        kw = dict(variables=tuple(out['energies']))
        if 'H-Output-1' in m.historyOutputRequests.keys():
            m.historyOutputRequests['H-Output-1'].setValues(**kw)
        else:
            m.HistoryOutputRequest(name='H-Output-1', createStepName=first, **kw)
    for h in out.get('history', []):
        kw = dict(name=h['name'], createStepName=h.get('step', first), variables=tuple(h['variables']),
                  region=a.sets[h['set']])
        if 'num_intervals' in h:
            kw['numIntervals'] = h['num_intervals']
        else:
            kw['frequency'] = h.get('frequency', 1)
        m.HistoryOutputRequest(**kw)


def write_job(spec, workdir, submit):
    js = spec.get('job', {})
    name = js.get('name', spec['model_name'])
    ncpu = js.get('cpus', 1)
    kw = dict(name=name, model=spec['model_name'], type=ANALYSIS, numCpus=ncpu, numDomains=ncpu,
              memory=90, memoryUnits=PERCENTAGE,
              explicitPrecision=DOUBLE_PLUS_PACK if js.get('double') else SINGLE,
              nodalOutputPrecision=FULL if js.get('double') else SINGLE)
    if name in mdb.jobs.keys():
        del mdb.jobs[name]
    j = mdb.Job(**kw)
    cwd = os.getcwd()
    os.chdir(workdir)
    try:
        j.writeInput(consistencyChecking=OFF)
        log('  wrote %s.inp' % name)
        if submit:
            log('  submitting %s inside CAE (holds the CAE licence token until it ends)' % name)
            j.submit(consistencyChecking=OFF)
            j.waitForCompletion()
            log('  job %s finished with status %s' % (name, j.status))
    finally:
        os.chdir(cwd)
    return name


# ----------------------------------------------------------------------------- main
def main():
    spec_path, submit = parse_args(sys.argv)
    spec = to_str(json.load(open(spec_path)))
    workdir = os.path.abspath(spec.get('workdir', os.path.dirname(os.path.abspath(spec_path))))
    if not os.path.isdir(workdir):
        os.makedirs(workdir)
    log('OhmFrame abaqus-model-builder: %s  (units %s)' % (spec['model_name'], spec.get('units', '?')))
    check_units(spec)

    Mdb()
    m = mdb.Model(name=spec['model_name'])
    if 'Model-1' in mdb.models.keys() and spec['model_name'] != 'Model-1':
        del mdb.models['Model-1']

    for ms in spec.get('materials', []):
        build_material(m, ms)
    for ss in spec.get('sections', []):
        build_section(m, ss)
    parts = {}
    for ps in spec['parts']:
        p = build_part(m, ps)
        partition_part(p, ps.get('partitions'))
        parts[ps['name']] = p
    for sa in spec.get('section_assignments', []):
        assign_section(parts[sa['part']], sa)
    mesh_info = {}
    for ms in spec.get('mesh', []):
        mesh_info[ms['part']] = mesh_part(parts[ms['part']], ms)

    a = build_instances(m, spec['instances'])
    a.regenerate()
    sizes = build_sets(m, a, spec)
    steps = spec['steps']
    build_steps(m, steps)
    if any(s['type'].startswith('heat') for s in steps):
        m.setValues(absoluteZero=spec.get('absolute_zero', -273.15))   # needed for film/radiation in degC
    build_amplitudes(m, spec.get('amplitudes'))
    build_bcs(m, a, spec.get('bcs', []))
    build_loads(m, a, spec.get('loads', []))
    build_predefined(m, a, spec.get('predefined', []))
    build_interactions(m, a, spec.get('interactions'), steps[0]['name'])
    build_outputs(m, a, spec.get('outputs', {}), steps)

    job = write_job(spec, workdir, submit)
    cae = os.path.join(workdir, spec.get('cae_name', spec['model_name']) + '.cae')
    mdb.saveAs(pathName=cae)
    manifest = dict(model=spec['model_name'], job=job, units=spec.get('units'), cae=os.path.basename(cae),
                    mesh=mesh_info, selections=sizes, steps=[s['name'] for s in steps],
                    abaqus_version=str(globals().get('version', 'unknown')))
    json.dump(manifest, open(os.path.join(workdir, job + '_model.json'), 'w'), indent=2, sort_keys=True)
    log('BUILT %s -> %s, %s.inp, %s_model.json' % (spec['model_name'], os.path.basename(cae), job, job))


main()
