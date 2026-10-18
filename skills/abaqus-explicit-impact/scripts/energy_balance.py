# -*- coding: utf-8 -*-
"""
energy_balance.py - is this Abaqus/Explicit result trustworthy? Reads the whole-model energy
history from an ODB and applies the standard checks. Plain Abaqus Python (no CAE licence):

    abaqus python energy_balance.py job.odb [--mode impact|quasistatic] [--step NAME]
                                            [--ke0 VALUE] [--out DIR]

Needs the default whole-model history (ALLKE, ALLIE, ALLAE, ALLWK, ETOTAL ...; DMASS and
ALLMW if mass scaling is used). Writes <out>/energies.csv and <out>/energy_checks.json and
prints PASS / WARN / FAIL per check.

Checks (thresholds are the usual rules of thumb, change them in LIMITS)
  hourglass      max ALLAE/ALLIE (after ALLIE reaches 1 % of its peak)   < 5 % pass, < 10 % warn
  energy drift   |ETOTAL(t) - ETOTAL(0)| / max(ALLKE, ALLIE, ALLWK)       < 1 % pass, < 5 % warn
  quasi-static   (mode quasistatic) max ALLKE/ALLIE over the 2nd half     < 5 % pass, < 10 % warn
  mass scaling   final DMASS (fractional mass change)                     < 2 % pass, < 5 % warn
                 ALLMW (work of mass scaling) / ALLIE                     < 1 % pass, < 5 % warn
  damping        ALLVD / max(ALLKE0, ALLIE)                               < 5 % pass, < 10 % warn
  initial KE     (--ke0 given) ALLKE at t=0 vs the hand value             < 1 % pass, < 5 % warn

A FAIL means the result is not usable as-is: refine/hourglass control, reduce mass scaling,
slow the loading (quasi-static), or use double precision for very long runs.

Python 2.7 and 3.  OhmFrame - https://ohmframe.com - MIT licence.
"""
from __future__ import print_function

import json
import os
import sys

from odbAccess import openOdb
try:
    import builtins as _bi
except ImportError:
    import __builtin__ as _bi
sum, min, max, round, abs = _bi.sum, _bi.min, _bi.max, _bi.round, _bi.abs

LIMITS = dict(hourglass=(0.05, 0.10), drift=(0.01, 0.05), quasistatic=(0.05, 0.10), dmass=(0.02, 0.05),
              mass_work=(0.01, 0.05), damping=(0.05, 0.10), ke0=(0.01, 0.05))
VARS = ('ALLKE', 'ALLIE', 'ALLAE', 'ALLVD', 'ALLFD', 'ALLWK', 'ALLPD', 'ALLSE', 'ALLDMD', 'ALLMW',
        'ETOTAL', 'DMASS')


def opt(argv, key, default=None):
    if key in argv:
        i = argv.index(key)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def grade(value, lim):
    if value is None:
        return 'N/A'
    return 'PASS' if value < lim[0] else ('WARN' if value < lim[1] else 'FAIL')


def main(argv):
    files = [a for a in argv if a.lower().endswith('.odb')]
    if not files:
        print(__doc__)
        return 2
    mode = opt(argv, '--mode', 'impact').lower()
    ke0 = opt(argv, '--ke0')
    out = opt(argv, '--out', os.path.splitext(os.path.basename(files[0]))[0] + '_energy')
    if not os.path.isdir(out):
        os.makedirs(out)
    odb = openOdb(files[0], readOnly=True)
    sname = opt(argv, '--step') or list(odb.steps.keys())[-1]
    step = odb.steps[sname]
    reg = None
    for k, r in step.historyRegions.items():
        if k.upper().startswith('ASSEMBLY') and 'ALLKE' in r.historyOutputs.keys():
            reg = r
            break
    if reg is None:
        print('no whole-model energy history in step %s (request ALLKE, ALLIE, ... on the whole model)' % sname)
        return 2
    data = {}
    for v in VARS:
        if v in reg.historyOutputs.keys():
            data[v] = [(t + step.totalTime, val) for t, val in reg.historyOutputs[v].data]
    times = [t for t, _ in data['ALLKE']]
    n = len(times)

    def col(v):
        if v not in data or len(data[v]) != n:
            return None
        return [val for _, val in data[v]]

    with open(os.path.join(out, 'energies.csv'), 'w') as fh:
        names = [v for v in VARS if col(v) is not None]
        fh.write('time,' + ','.join(names) + '\n')
        for i in range(n):
            fh.write('%.8g,' % times[i] + ','.join('%.8g' % col(v)[i] for v in names) + '\n')

    ke, ie, ae, wk, et = col('ALLKE'), col('ALLIE'), col('ALLAE'), col('ALLWK'), col('ETOTAL')
    vd, mw, dm = col('ALLVD'), col('ALLMW'), col('DMASS')
    res = dict(odb=os.path.basename(files[0]), step=sname, mode=mode, points=n, t_end=times[-1], checks={})
    ie_peak = max(ie) if ie else 0.0
    scale = max([max(ke) if ke else 0.0, ie_peak, max(abs(x) for x in wk) if wk else 0.0]) or 1.0

    def add(name, value, lim, note):
        res['checks'][name] = dict(value=value, verdict=grade(value, lim), limits=lim, note=note)

    if ae and ie_peak > 0:
        idx = [i for i in range(n) if ie[i] > 0.01 * ie_peak]
        add('hourglass', max(ae[i] / ie[i] for i in idx) if idx else None, LIMITS['hourglass'],
            'ALLAE/ALLIE; high -> refine, enhanced hourglass control, or fully integrated elements')
    if et:
        add('drift', max(abs(x - et[0]) for x in et) / scale, LIMITS['drift'],
            'ETOTAL change / max energy; high -> contact problems, mass scaling, or single precision on a long run')
    if mode.startswith('quasi') and ke and ie:
        half = [i for i in range(n // 2, n) if ie[i] > 0]
        add('quasistatic', max(ke[i] / ie[i] for i in half) if half else None, LIMITS['quasistatic'],
            'ALLKE/ALLIE over the second half; high -> load too fast, use smooth-step amplitude or longer time')
    if dm:
        # DMASS is a PERCENTAGE change of total mass (same number as the CHNG MASS column of the
        # .sta), not a fraction - checked against Abaqus 2023. Convert before comparing to LIMITS.
        add('dmass', abs(dm[-1]) / 100.0, LIMITS['dmass'],
            'fraction of mass added by mass scaling (DMASS/100; DMASS is a percentage)')
    if mw and ie_peak > 0:
        add('mass_work', abs(mw[-1]) / ie_peak, LIMITS['mass_work'], 'ALLMW/ALLIE: energy injected by mass scaling')
    if vd:
        add('damping', abs(vd[-1]) / scale, LIMITS['damping'], 'ALLVD (bulk viscosity) share')
    if ke0 is not None and ke:
        k0 = float(ke0)
        add('ke0', abs(ke[0] - k0) / k0 if k0 else None, LIMITS['ke0'], 'initial ALLKE vs hand value %.6g' % k0)
    res['peaks'] = dict(ALLKE=max(ke) if ke else None, ALLIE=ie_peak, ALLWK_final=wk[-1] if wk else None,
                        ALLKE_final=ke[-1] if ke else None, ALLIE_final=ie[-1] if ie else None)
    verdicts = [c['verdict'] for c in res['checks'].values()]
    res['overall'] = 'FAIL' if 'FAIL' in verdicts else ('WARN' if 'WARN' in verdicts else 'PASS')
    json.dump(res, open(os.path.join(out, 'energy_checks.json'), 'w'), indent=2)
    odb.close()
    for k in sorted(res['checks']):
        c = res['checks'][k]
        v = c['value']
        print('%-12s %-5s %s   (%s)' % (k, c['verdict'], 'n/a' if v is None else '%.3f %%' % (100.0 * v), c['note']))
    print('peaks: %s' % res['peaks'])
    print('OVERALL: %s  -> %s' % (res['overall'], out))
    return 0 if res['overall'] != 'FAIL' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
