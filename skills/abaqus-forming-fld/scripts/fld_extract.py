# -*- coding: utf-8 -*-
"""
fld_extract.py - forming-limit post-processing for Abaqus shell models with FLD damage
initiation. Plain Abaqus Python (no CAE licence):

    abaqus python fld_extract.py job.odb [--step NAME] [--rp-set RP_PUNCH] [--set BLANK_SET]
                                         [--frame N] [--out DIR]

Per frame (fld_history.csv): time, max FLD criterion (FLDCRT or any FLD*CRT field), number of
elements with the criterion >= 1, number of deleted elements (STATUS = 0), punch displacement
and force (with --rp-set: read from the first node history region carrying U3, i.e. request
U3/RF3 history only on the punch reference point, as build_dome_stretch.py does).
Onset (summary.json): first frame with max criterion >= 1 = predicted necking onset;
first frame with a deleted element = predicted fracture; punch stroke and force at both.
Strains (strains_<frame>.csv): for the onset frame (or --frame), per element and section point,
major/minor in-plane logarithmic strain, criterion value and STATUS - ready to overlay on the FLC.
Deleted elements (STATUS = 0) are excluded from the "max" values but kept in the CSV.

Python 2.7 and 3.  OhmFrame - https://ohmframe.com - MIT licence.
"""
from __future__ import print_function

import json
import math
import os
import sys

from odbAccess import openOdb
try:
    import builtins as _bi
except ImportError:
    import __builtin__ as _bi
sum, min, max, round, abs = _bi.sum, _bi.min, _bi.max, _bi.round, _bi.abs


def opt(argv, key, default=None):
    if key in argv:
        i = argv.index(key)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def crit_name(frame):
    for k in frame.fieldOutputs.keys():
        if k.upper() == 'FLDCRT':
            return k
    for k in frame.fieldOutputs.keys():
        if k.upper().startswith('FLD') and k.upper().endswith('CRT'):
            return k
    return None


def principal_2d(d):
    """major, minor from in-plane LE11, LE22, LE12 (engineering shear, as Abaqus outputs)."""
    e11, e22 = d[0], d[1]
    g12 = d[3] if len(d) > 3 else (d[2] if len(d) == 3 else 0.0)
    c = 0.5 * (e11 + e22)
    r = math.sqrt((0.5 * (e11 - e22)) ** 2 + (0.5 * g12) ** 2)
    return c + r, c - r


def key_of(v):
    sp = v.sectionPoint.number if v.sectionPoint else 0
    return (v.instance.name if v.instance else '', v.elementLabel, v.integrationPoint, sp)


def subset(field, region):
    return field.getSubset(region=region) if region is not None else field


def main(argv):
    files = [a for a in argv if a.lower().endswith('.odb')]
    if not files:
        print(__doc__)
        return 2
    out = opt(argv, '--out', os.path.splitext(os.path.basename(files[0]))[0] + '_fld')
    if not os.path.isdir(out):
        os.makedirs(out)
    odb = openOdb(files[0], readOnly=True)
    sname = opt(argv, '--step') or list(odb.steps.keys())[-1]
    step = odb.steps[sname]
    region = None
    if opt(argv, '--set'):
        nm = opt(argv, '--set').upper()
        sets = odb.rootAssembly.elementSets
        region = sets[nm] if nm in sets.keys() else None
        if region is None:
            for inst in odb.rootAssembly.instances.values():
                if nm in inst.elementSets.keys():
                    region = inst.elementSets[nm]
    # punch history
    hist = {}
    rp = opt(argv, '--rp-set')
    if rp:
        for hk, hr in step.historyRegions.items():
            if hk.startswith('Node'):
                try:
                    pt = hr.point
                    ok = pt.node is not None
                except Exception:
                    ok = False
                if ok and 'U3' in hr.historyOutputs.keys():
                    hist['U3'] = hr.historyOutputs['U3'].data
                    if 'RF3' in hr.historyOutputs.keys():
                        hist['RF3'] = hr.historyOutputs['RF3'].data
                    break

    def at(var, t):
        d = hist.get(var)
        if not d:
            return None
        best = min(d, key=lambda p: abs(p[0] - t))
        return best[1]

    rows, onset, fracture = [], None, None
    for fi, fr in enumerate(step.frames):
        cn = crit_name(fr)
        status = {}
        if 'STATUS' in fr.fieldOutputs.keys():
            for v in subset(fr.fieldOutputs['STATUS'], region).values:
                k = (v.instance.name if v.instance else '', v.elementLabel)
                status[k] = min(status.get(k, 1.0), v.data)
        deleted = sum(1 for s in status.values() if s == 0.0)
        cmax, n_over = 0.0, set()
        if cn:
            for v in subset(fr.fieldOutputs[cn], region).values:
                k = (v.instance.name if v.instance else '', v.elementLabel)
                if status.get(k, 1.0) == 0.0:
                    continue
                if v.data > cmax:
                    cmax = v.data
                if v.data >= 1.0:
                    n_over.add(k)
        t = fr.frameValue
        rows.append((fi, t, cmax, len(n_over), deleted, at('U3', t), at('RF3', t)))
        if onset is None and cmax >= 1.0:
            onset = fi
        if fracture is None and deleted > 0:
            fracture = fi
    with open(os.path.join(out, 'fld_history.csv'), 'w') as fh:
        fh.write('frame,time,max_criterion,elements_over_1,deleted,punch_U3,punch_RF3\n')
        for r in rows:
            fh.write(','.join('' if x is None else ('%.8g' % x if isinstance(x, float) else str(x)) for x in r) + '\n')

    fsel = opt(argv, '--frame')
    fidx = int(fsel) if fsel is not None else (onset if onset is not None else len(step.frames) - 1)
    fr = step.frames[fidx]
    cn = crit_name(fr)
    crit = {}
    if cn:
        for v in subset(fr.fieldOutputs[cn], region).values:
            crit[key_of(v)] = v.data
    st = {}
    if 'STATUS' in fr.fieldOutputs.keys():
        for v in subset(fr.fieldOutputs['STATUS'], region).values:
            st[(v.instance.name if v.instance else '', v.elementLabel)] = v.data
    n_pts, emax = 0, None
    with open(os.path.join(out, 'strains_frame%d.csv' % fidx), 'w') as fh:
        fh.write('instance,element,ip,section_point,major,minor,criterion,status\n')
        if 'LE' in fr.fieldOutputs.keys():
            for v in subset(fr.fieldOutputs['LE'], region).values:
                try:
                    mj, mn = v.maxInPlanePrincipal, v.minInPlanePrincipal
                    if mj is None or mn is None:
                        raise AttributeError
                except AttributeError:
                    mj, mn = principal_2d(v.data)
                k = key_of(v)
                s = st.get(k[:2], 1.0)
                c = crit.get(k)
                fh.write('%s,%d,%d,%d,%.6g,%.6g,%s,%g\n' % (k[0], k[1], k[2], k[3], mj, mn,
                                                         '' if c is None else '%.6g' % c, s))
                n_pts += 1
                if s != 0.0 and (emax is None or mj > emax[0]):
                    emax = (mj, mn, k[1])
    summary = dict(odb=os.path.basename(files[0]), step=sname, criterion_field=cn, frames=len(rows),
                   onset_frame=onset, onset_time=rows[onset][1] if onset is not None else None,
                   onset_punch_U3=rows[onset][5] if onset is not None else None,
                   fracture_frame=fracture, fracture_time=rows[fracture][1] if fracture is not None else None,
                   fracture_punch_U3=rows[fracture][5] if fracture is not None else None,
                   max_punch_force=max([abs(r[6]) for r in rows if r[6] is not None] or [None]) if hist else None,
                   strain_frame=fidx, strain_points=n_pts,
                   max_major_at_strain_frame=None if emax is None else dict(major=emax[0], minor=emax[1],
                                                                              element=emax[2]))
    json.dump(summary, open(os.path.join(out, 'summary.json'), 'w'), indent=2)
    odb.close()
    for k in sorted(summary):
        print('%-26s %s' % (k, summary[k]))
    if cn is None:
        print('WARNING: no FLD criterion field found - request DMICRT (or FLDCRT) in the field output')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
