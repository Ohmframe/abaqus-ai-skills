# -*- coding: utf-8 -*-
"""
odb_extract.py - generic Abaqus ODB post-processing to CSV + JSON (run with abaqus python).

    abaqus python odb_extract.py JOB.odb [options]

Options (all repeatable where it makes sense):
  --step NAME             step to read (default: last step)
  --frame N               frame index for field output (default: -1 = last); 'all' = every frame
  --field VAR[:COMP]      field output, e.g. S:MISES  S:S11  U:MAGNITUDE  U:U2  PEEQ  NT11  HFL:HFL1
  --region NAME           restrict --field to an instance or set (case-insensitive)
  --reactions SET         sum RF (and RM) over a node set, every frame -> reactions_<SET>.csv
  --history-set SET       dump every history output of the regions of a node set / RP set
  --history-var VAR       limit --history-set to these variables (default: all)
  --energies              whole-model energies (ALLKE, ALLIE, ALLAE, ALLWK, ETOTAL ...) + ratios
  --contact               contact force histories (CFN*, CFS*), de-duplicated A/B vs B/A
  --out DIR               output folder (default: <job>_post)

Writes into DIR:
  summary.json                         every max/min with its location, reaction sums, energy checks
  field_<VAR>_<COMP>_<step>_f<k>.csv   instance, label, position, value
  reactions_<SET>.csv                  time, RF1, RF2, RF3, RM1, RM2, RM3 (summed)
  history_<region>.csv                 time + one column per variable
  energies.csv, contact_forces.csv

No CAE licence token is used. Runs under Abaqus Python 2.7 (<= 2023) and 3 (2024+).
ODB names are upper-case: instance 'Beam-1' becomes 'BEAM-1'. Lookups here ignore case.

OhmFrame - https://ohmframe.com - MIT licence. Verify every result yourself.
"""
from __future__ import print_function

import json
import math
import os
import sys

from odbAccess import openOdb
import abaqusConstants as C

try:
    import builtins as _bi
except ImportError:
    import __builtin__ as _bi
sum, min, max, abs = _bi.sum, _bi.min, _bi.max, _bi.abs

INVARIANTS = {
    'MISES': 'MISES', 'TRESCA': 'TRESCA', 'PRESS': 'PRESS', 'MAGNITUDE': 'MAGNITUDE',
    'MAX_PRINCIPAL': 'MAX_PRINCIPAL', 'MID_PRINCIPAL': 'MID_PRINCIPAL', 'MIN_PRINCIPAL': 'MIN_PRINCIPAL',
    'MAX_INPLANE_PRINCIPAL': 'MAX_INPLANE_PRINCIPAL', 'MIN_INPLANE_PRINCIPAL': 'MIN_INPLANE_PRINCIPAL',
}
ENERGIES = ('ALLKE', 'ALLIE', 'ALLSE', 'ALLPD', 'ALLAE', 'ALLVD', 'ALLFD', 'ALLDMD', 'ALLWK',
            'ALLMW', 'ALLCD', 'ETOTAL', 'DMASS')


# ----------------------------------------------------------------------------- cli
def parse(argv):
    o = dict(odb=None, step=None, frame='-1', fields=[], region=None, reactions=[], hsets=[],
             hvars=[], energies=False, contact=False, out=None)
    multi = {'--field': 'fields', '--reactions': 'reactions', '--history-set': 'hsets',
             '--history-var': 'hvars'}
    single = {'--step': 'step', '--frame': 'frame', '--region': 'region', '--out': 'out'}
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in multi:
            o[multi[a]].append(argv[i + 1]); i += 2
        elif a in single:
            o[single[a]] = argv[i + 1]; i += 2
        elif a == '--energies':
            o['energies'] = True; i += 1
        elif a == '--contact':
            o['contact'] = True; i += 1
        elif a.lower().endswith('.odb'):
            o['odb'] = a; i += 1
        else:
            raise SystemExit('unknown argument %s\n%s' % (a, __doc__))
    if not o['odb']:
        raise SystemExit(__doc__)
    if not o['out']:
        o['out'] = os.path.splitext(o['odb'])[0] + '_post'
    return o


def safe_name(s):
    return ''.join(c if c.isalnum() or c in '-_.' else '_' for c in s)


def write_csv(path, header, rows):
    with open(path, 'w') as fh:
        fh.write(','.join(header) + '\n')
        for r in rows:
            fh.write(','.join(('%.8g' % v) if isinstance(v, float) else str(v) for v in r) + '\n')


# ----------------------------------------------------------------------------- lookups
def ci_get(repo, name):
    """Case-insensitive repository lookup (ODB upper-cases names)."""
    if name in repo.keys():
        return repo[name]
    for k in repo.keys():
        if k.upper() == name.upper():
            return repo[k]
    return None


def find_region(odb, name):
    ra = odb.rootAssembly
    for repo in (ra.instances, ra.nodeSets, ra.elementSets):
        r = ci_get(repo, name)
        if r is not None:
            return r
    for inst in ra.instances.values():
        for repo in (inst.nodeSets, inst.elementSets):
            r = ci_get(repo, name)
            if r is not None:
                return r
    raise KeyError('no instance or set named %s in the ODB. Instances: %s; assembly node sets: %s'
                   % (name, list(ra.instances.keys()), list(ra.nodeSets.keys())))


def find_nodeset(odb, name):
    ra = odb.rootAssembly
    r = ci_get(ra.nodeSets, name)
    if r is not None:
        return r
    for inst in ra.instances.values():
        r = ci_get(inst.nodeSets, name)
        if r is not None:
            return r
    raise KeyError('no node set %s. Assembly node sets: %s' % (name, list(ra.nodeSets.keys())))


def nodeset_region_names(ns):
    """History regions are named 'Node INSTANCE.label' (or 'Node ASSEMBLY.label' for RPs)."""
    names = []
    for block in ns.nodes:
        for n in block:
            inst = getattr(n, 'instanceName', None) or 'ASSEMBLY'
            names.append('Node %s.%d' % (inst, n.label))
    return names


# ----------------------------------------------------------------------------- field output
def subset_region(fo, region, var):
    """Restrict a field to a region.

    An integration-point field (S, E, PEEQ ...) cannot be subset by a NODE set: Abaqus returns an
    empty field, and the later getScalarField() then fails with the useless 'Invalid component
    label'. Retry at ELEMENT_NODAL, which is what you want anyway when you ask for stress 'at'
    a node set (the values are extrapolated to the nodes, so at a stress concentration they
    overshoot the integration-point peak).
    """
    sub = fo.getSubset(region=region)
    if len(sub.values):
        return sub
    try:
        sub2 = fo.getSubset(region=region, position=C.ELEMENT_NODAL)
    except Exception:
        sub2 = None
    if sub2 is not None and len(sub2.values):
        print('  NOTE: %s is an integration-point field; the region is a node set, so values are '
              'extrapolated to the nodes (ELEMENT_NODAL)' % var)
        return sub2
    raise KeyError('field %s has no values in the requested --region. Check that the set belongs to '
                   'the right kind of entity (element/integration-point fields need an element set '
                   'or an instance; nodal fields need a node set).' % var)


def scalar_values(fo, comp):
    """Return (values, getter) where getter(v) gives a float."""
    if comp is None:
        if fo.type == C.SCALAR:
            return fo.values, lambda v: float(v.data)
        comp = 'MAGNITUDE' if 'MAGNITUDE' in [str(x) for x in fo.validInvariants] else 'MISES'
    cu = comp.upper()
    if cu in INVARIANTS:
        sub = fo.getScalarField(invariant=getattr(C, INVARIANTS[cu]))
        return sub.values, lambda v: float(v.data)
    labels = [str(x) for x in fo.componentLabels]
    if cu in [x.upper() for x in labels]:
        sub = fo.getScalarField(componentLabel=labels[[x.upper() for x in labels].index(cu)])
        return sub.values, lambda v: float(v.data)
    raise KeyError('component/invariant %s not available. Components %s, invariants %s'
                   % (comp, labels, [str(x) for x in fo.validInvariants]))


def field_extract(odb, step, frames, spec, region, outdir):
    var, comp = (spec.split(':', 1) + [None])[:2]
    results = []
    for k in frames:
        fr = step.frames[k]
        if var not in fr.fieldOutputs.keys():
            raise KeyError('field %s not in frame %d. Available: %s'
                           % (var, k, sorted(fr.fieldOutputs.keys())))
        fo = fr.fieldOutputs[var]
        if region is not None:
            fo = subset_region(fo, region, var)
        vals, get = scalar_values(fo, comp)
        rows, vmax, vmin = [], None, None
        for v in vals:
            x = get(v)
            label = v.elementLabel if v.elementLabel is not None else v.nodeLabel
            inst = v.instance.name if v.instance is not None else 'ASSEMBLY'
            rows.append((inst, label, str(v.position), x))
            if vmax is None or x > vmax[0]:
                vmax = (x, inst, label)
            if vmin is None or x < vmin[0]:
                vmin = (x, inst, label)
        name = 'field_%s_%s_%s_f%d.csv' % (safe_name(var), safe_name(comp or 'value'), safe_name(step.name), k)
        write_csv(os.path.join(outdir, name), ('instance', 'label', 'position', 'value'), rows)
        res = dict(variable=var, component=comp, frame=k, frame_value=fr.frameValue, count=len(rows),
                   csv=name)
        if vmax:
            res.update(max=vmax[0], max_at='%s.%s' % vmax[1:], min=vmin[0], min_at='%s.%s' % vmin[1:])
        results.append(res)
        print('  %-14s frame %3d t=%-10.4g max %-12.5g at %-18s min %-12.5g at %s'
              % (spec, k, fr.frameValue, res.get('max', float('nan')), res.get('max_at', '-'),
                 res.get('min', float('nan')), res.get('min_at', '-')))
    return results


# ----------------------------------------------------------------------------- reactions
def reactions(odb, step, setname, outdir):
    ns = find_nodeset(odb, setname)
    rows = []
    for fr in step.frames:
        tot = [0.0] * 6
        for var, off in (('RF', 0), ('RM', 3)):
            if var not in fr.fieldOutputs.keys():
                continue
            for v in fr.fieldOutputs[var].getSubset(region=ns).values:
                for i, x in enumerate(v.data):
                    if i < 3:
                        tot[off + i] += float(x)
        rows.append([fr.frameValue] + tot)
    name = 'reactions_%s.csv' % safe_name(setname)
    write_csv(os.path.join(outdir, name), ('time', 'RF1', 'RF2', 'RF3', 'RM1', 'RM2', 'RM3'), rows)
    last = rows[-1] if rows else [0.0] * 7
    peak = [max(abs(r[i]) for r in rows) if rows else 0.0 for i in range(1, 7)]
    print('  reactions %-12s last RF = (%.5g, %.5g, %.5g)  peak |RF| = (%.5g, %.5g, %.5g)'
          % (setname, last[1], last[2], last[3], peak[0], peak[1], peak[2]))
    return dict(set=setname, csv=name, last=dict(zip(('RF1', 'RF2', 'RF3', 'RM1', 'RM2', 'RM3'), last[1:])),
                peak_abs=dict(zip(('RF1', 'RF2', 'RF3', 'RM1', 'RM2', 'RM3'), peak)))


# ----------------------------------------------------------------------------- history
def history_dump(step, region_name, hvars, outdir):
    reg = step.historyRegions[region_name]
    names = [k for k in reg.historyOutputs.keys() if not hvars or k.split()[0] in hvars]
    if not names:
        return None
    times = [t for t, _ in reg.historyOutputs[names[0]].data]
    cols = dict((n, dict(reg.historyOutputs[n].data)) for n in names)
    rows = [[t] + [cols[n].get(t, float('nan')) for n in names] for t in times]
    fname = 'history_%s.csv' % safe_name(region_name)
    write_csv(os.path.join(outdir, fname), ['time'] + names, rows)
    ext = {}
    for n in names:
        vals = [v for _, v in reg.historyOutputs[n].data]
        ext[n] = dict(last=vals[-1], max=max(vals), min=min(vals))
    return dict(region=region_name, csv=fname, values=ext)


def energies(step, outdir):
    reg = None
    for k in step.historyRegions.keys():
        if k.startswith('Assembly'):
            reg = step.historyRegions[k]
    if reg is None:
        return dict(error='no Assembly history region: request ALLKE, ALLIE, ... in H-Output-1')
    have = [e for e in ENERGIES if e in reg.historyOutputs.keys()]
    if not have:
        return dict(error='no energy history outputs found')
    data = dict((e, reg.historyOutputs[e].data) for e in have)
    times = [t for t, _ in data[have[0]]]
    rows = [[times[i]] + [data[e][i][1] if i < len(data[e]) else float('nan') for e in have]
            for i in range(len(times))]
    write_csv(os.path.join(outdir, 'energies.csv'), ['time'] + have, rows)
    last = dict((e, data[e][-1][1]) for e in have)
    out = dict(csv='energies.csv', last=last)
    T = step.timePeriod

    def series(e):
        return [v for _, v in data[e]] if e in data else None
    ke, ie, ae, et = series('ALLKE'), series('ALLIE'), series('ALLAE'), series('ETOTAL')
    if ke and ie:
        r = [k / i for (t, _), k, i in zip(data['ALLKE'], ke, ie) if i > 1e-12 and t > 0.2 * T]
        out['max_KE_over_IE_after_20pct'] = max(r) if r else None
    if ae and ie and ie[-1] > 0:
        out['AE_over_IE_end'] = ae[-1] / ie[-1]
    if et:
        ref = max([abs(x) for x in (ke or [0.0]) + (ie or [0.0])] + [1e-30])
        out['ETOTAL_drift_over_max_energy'] = (et[-1] - et[0]) / ref
    print('  energies end: %s' % ', '.join('%s=%.4g' % (k, v) for k, v in sorted(last.items())))
    for k in ('max_KE_over_IE_after_20pct', 'AE_over_IE_end', 'ETOTAL_drift_over_max_energy'):
        if out.get(k) is not None:
            print('  %-32s %.4f' % (k, out[k]))
    return out


def contact_forces(step, outdir):
    """CFN/CFS histories are written once per surface view (A/B and B/A): keep one of each pair."""
    seen, cols = set(), []
    for rname, reg in step.historyRegions.items():
        for oname, ho in reg.historyOutputs.items():
            if not (oname.startswith('CFN') or oname.startswith('CFS') or oname.startswith('CFT')):
                continue
            var, _, tail = oname.partition(' ')
            key = (var, tuple(sorted(tail.strip().split('/'))))
            if key in seen:
                continue
            seen.add(key)
            cols.append((oname, ho.data))
    if not cols:
        return dict(error='no CFN/CFS history: request them per interaction (one interaction per request)')
    times = [t for t, _ in cols[0][1]]
    rows = [[times[i]] + [c[1][i][1] if i < len(c[1]) else float('nan') for c in cols]
            for i in range(len(times))]
    write_csv(os.path.join(outdir, 'contact_forces.csv'), ['time'] + [c[0] for c in cols], rows)
    peaks = dict((c[0], max(abs(v) for _, v in c[1])) for c in cols)
    for k, v in sorted(peaks.items()):
        print('  contact %-50s peak |F| %.5g' % (k, v))
    return dict(csv='contact_forces.csv', series=len(cols), peak_abs=peaks)


# ----------------------------------------------------------------------------- main
def main():
    o = parse(sys.argv)
    if not os.path.isdir(o['out']):
        os.makedirs(o['out'])
    odb = openOdb(path=o['odb'], readOnly=True)
    try:
        sname = o['step'] or list(odb.steps.keys())[-1]
        step = ci_get(odb.steps, sname)
        if step is None:
            raise KeyError('no step %s. Steps: %s' % (sname, list(odb.steps.keys())))
        nfr = len(step.frames)
        frames = list(range(nfr)) if o['frame'] == 'all' else [int(o['frame']) % nfr]
        print('OhmFrame odb_extract: %s  step %s (%d frames)' % (o['odb'], step.name, nfr))
        summary = dict(odb=os.path.basename(o['odb']), step=step.name, frames=nfr,
                       steps=list(odb.steps.keys()), instances=list(odb.rootAssembly.instances.keys()),
                       node_sets=list(odb.rootAssembly.nodeSets.keys()), fields=[], reactions=[],
                       history=[])
        region = find_region(odb, o['region']) if o['region'] else None
        for spec in o['fields']:
            summary['fields'] += field_extract(odb, step, frames, spec, region, o['out'])
        for s in o['reactions']:
            summary['reactions'].append(reactions(odb, step, s, o['out']))
        for s in o['hsets']:
            names = nodeset_region_names(find_nodeset(odb, s))
            for rn in names:
                if rn in step.historyRegions.keys():
                    h = history_dump(step, rn, o['hvars'], o['out'])
                    if h:
                        h['set'] = s
                        summary['history'].append(h)
            if not any(h.get('set') == s for h in summary['history']):
                print('  WARNING: no history region for set %s (did you request history output on it?)' % s)
        if o['energies']:
            summary['energies'] = energies(step, o['out'])
        if o['contact']:
            summary['contact'] = contact_forces(step, o['out'])
        with open(os.path.join(o['out'], 'summary.json'), 'w') as fh:
            json.dump(summary, fh, indent=2, sort_keys=True, default=str)
        print('wrote %s' % os.path.join(o['out'], 'summary.json'))
    finally:
        odb.close()


if __name__ == '__main__':
    main()
