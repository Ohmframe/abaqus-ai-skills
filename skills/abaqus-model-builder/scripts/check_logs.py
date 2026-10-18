#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check_logs.py - triage an Abaqus job from its text logs (.log, .sta, .msg, .dat).

    python check_logs.py JOBNAME [--dir RUN_DIR] [--json out.json]

Plain Python 2.7 or 3 (no Abaqus needed), so it also runs on a laptop that only has
the log files. Exit code: 0 = completed with no errors, 1 = errors or not completed,
2 = no log files found.

What it reports
  * completion status from .log / .sta
  * ***ERROR and ***WARNING counts per file, grouped by message (numbers masked)
  * known-message explanations (what usually causes it and what to try)
  * model size from .dat (nodes, elements, variables)
  * Standard: increments, cutbacks (attempts marked U), last step time
  * Explicit: last .sta row, stable increment, mass change %, energy drift

OhmFrame - https://ohmframe.com - MIT licence.
"""
from __future__ import print_function

import json
import os
import re
import sys

KNOWN = [
    (r'zero pivot|numerical singularity',
     'Unrestrained rigid-body mode. Check BCs, missing ties or contact that is open at the start, '
     'and parts held only by contact. Add soft springs or contact stabilisation if needed.'),
    (r'negative eigenvalue',
     'Loss of stiffness (buckling, yielding, contact chatter). Fine if expected; otherwise refine '
     'load incrementation or use Riks / stabilisation.'),
    (r'time increment required is less than the minimum|too many attempts',
     'Convergence failure. Look at the increment where it failed in .msg: contact, plasticity or '
     'distortion. Reduce initial increment, add stabilisation, fix the contact set-up.'),
    (r'excessive(ly)? distort',
     'Elements turned inside out. Usual causes: damage localisation without deletion, hourglassing, '
     'contact penetration, too-coarse mesh at the impact zone.'),
    (r'will not be tied|not been tied|cannot be tied',
     'Tie found no partner within the position tolerance. Expected if the tolerance is chosen to '
     'pick only touching nodes; otherwise increase it or fix the geometry gap.'),
    (r'overconstraint|over-constrain',
     'Two constraints act on the same DOF (tie + BC, coupling + tie). Abaqus may remove one; check '
     'which one it kept.'),
    (r'300000 increments|round-off',
     'Long explicit run: use double precision (double=both / explicitPrecision=DOUBLE_PLUS_PACK).'),
    (r'strain increment has exceeded fifty times',
     'Very large plastic increment. Reduce the increment size or check units of the flow curve.'),
    (r'penetrat',
     'Contact overclosure/penetration. Check initial gaps, surface normals and shell thickness offsets.'),
    (r'distorted elements|aspect ratio|angle',
     'Mesh quality warning from the pre-processor. Run abaqus-mesh-doctor on the part.'),
    (r'license|licence|flexnet|checkout',
     'Licence problem (token count, server lost). Long runs die if the licence server drops.'),
    (r'sigterm|terminated by|killed',
     'The job was killed from outside (user, scheduler, closed shell, lost licence). Not a model '
     'error. Rerun detached; use restart output for long explicit runs.'),
]

NUM = re.compile(r'[-+]?\d+(\.\d+)?([eEdD][-+]?\d+)?')


def read(path):
    if not os.path.isfile(path):
        return None
    with open(path, 'rb') as fh:
        raw = fh.read()
    return raw.decode('latin-1')


def messages(text, tag):
    """Group ***ERROR / ***WARNING blocks by their first line, numbers masked."""
    groups = {}
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if tag in ln.upper():
            body = ln.split(':', 1)[-1].strip()
            if not body and i + 1 < len(lines):
                body = lines[i + 1].strip()
            key = NUM.sub('#', body)[:160]
            groups[key] = groups.get(key, 0) + 1
    return groups


def explain(msg):
    for pat, hint in KNOWN:
        if re.search(pat, msg, re.I):
            return hint
    return None


def dat_size(text):
    out = {}
    for key in ('NUMBER OF ELEMENTS IS', 'NUMBER OF NODES IS', 'TOTAL NUMBER OF VARIABLES IN THE MODEL'):
        m = re.search(re.escape(key) + r'\s+(\d+)', text)
        if m:
            out[key.lower().replace(' ', '_')] = int(m.group(1))
    return out


def sta_standard(text):
    incs, cutbacks, last_time = 0, 0, None
    for ln in text.splitlines():
        parts = ln.split()
        if len(parts) >= 8 and parts[0].isdigit() and parts[1].isdigit():
            att = parts[2]
            if att.endswith('U'):
                cutbacks += 1
            else:
                incs += 1
            try:
                last_time = float(parts[6])
            except ValueError:
                pass
    return dict(increments=incs, cutbacks=cutbacks, last_total_time=last_time)


def _num(tok):
    try:
        return float(tok.replace('D', 'E').replace('d', 'e'))
    except ValueError:
        return None


def sta_explicit(text):
    """Explicit .sta rows end with: stable inc, critical element, KE, total energy, % mass change.
    Older releases have no wallclock column; counting from the end works for both layouts."""
    rows = []
    for ln in text.splitlines():
        parts = ln.split()
        if len(parts) >= 7 and parts[0].isdigit() and _num(parts[-1]) is not None \
                and _num(parts[-2]) is not None and _num(parts[-5]) is not None:
            rows.append(parts)
    if not rows:
        return {}
    first, last = rows[0], rows[-1]
    e0, e1 = _num(first[-2]), _num(last[-2])
    ke_max = max(_num(r[-3]) for r in rows)
    out = dict(increments=int(last[0]), total_time_last=_num(last[1]),
               stable_increment_first=_num(first[-5]), stable_increment_last=_num(last[-5]),
               critical_element_last=last[-4], percent_mass_change_last=_num(last[-1]),
               total_energy_first=e0, total_energy_last=e1, kinetic_energy_max=ke_max)
    if ke_max:
        out['total_energy_drift_vs_max_KE_pct'] = 100.0 * (e1 - e0) / ke_max
    return out


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    job = argv[1]
    d = argv[argv.index('--dir') + 1] if '--dir' in argv else '.'
    jpath = argv[argv.index('--json') + 1] if '--json' in argv else None
    base = os.path.join(d, job)
    texts = dict((ext, read(base + '.' + ext)) for ext in ('log', 'sta', 'msg', 'dat'))
    if not any(texts.values()):
        print('no .log/.sta/.msg/.dat found for %s in %s' % (job, os.path.abspath(d)))
        return 2

    rep = dict(job=job, completed=None, files={})
    log = texts['log'] or ''
    sta = texts['sta'] or ''
    if 'COMPLETED' in log.upper() and 'ERROR' not in log.upper():
        rep['completed'] = True
    if 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' in sta.upper():
        rep['completed'] = True
    if 'HAS NOT BEEN COMPLETED' in sta.upper() or 'EXITED WITH ERROR' in log.upper():
        rep['completed'] = False
    # A datacheck run writes no .log and no .sta at all (checked on Abaqus 2023): the only
    # completion marker is in the .dat. Without this the triage of a clean datacheck reported
    # 'completed: None' and exited 1.
    if rep['completed'] is None and 'ANALYSIS DATACHECK COMPLETE' in (texts['dat'] or '').upper():
        rep['completed'] = True
        rep['datacheck'] = True

    n_err = 0
    for ext in ('log', 'msg', 'dat', 'sta'):
        t = texts[ext]
        if not t:
            continue
        e, w = messages(t, '***ERROR'), messages(t, '***WARNING')
        n_err += sum(e.values())
        rep['files'][ext] = dict(errors=e, warnings=w)
    if texts['dat']:
        rep['model_size'] = dat_size(texts['dat'])
    if sta:
        rep['sta'] = sta_explicit(sta) if 'STABLE' in sta.upper() else sta_standard(sta)

    print('=' * 78)
    print('JOB %s   completed: %s   errors: %d' % (job, rep['completed'], n_err))
    if 'model_size' in rep:
        print('model size: %s' % rep['model_size'])
    if 'sta' in rep:
        print('sta: %s' % rep['sta'])
    for ext, r in rep['files'].items():
        for tag in ('errors', 'warnings'):
            for msg, cnt in sorted(r[tag].items(), key=lambda kv: -kv[1]):
                print('[%s %s x%d] %s' % (ext, tag[:-1].upper(), cnt, msg))
                hint = explain(msg)
                if hint:
                    print('    -> %s' % hint)
    if jpath:
        with open(jpath, 'w') as fh:
            json.dump(rep, fh, indent=2, sort_keys=True)
    return 0 if (rep['completed'] and n_err == 0) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
