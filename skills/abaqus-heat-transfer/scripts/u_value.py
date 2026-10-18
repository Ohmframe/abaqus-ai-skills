# -*- coding: utf-8 -*-
"""
u_value.py - area-averaged heat flux and U-value from an Abaqus heat-transfer ODB.
Plain Abaqus Python (no CAE licence):

    abaqus python u_value.py job.odb --set ALL_LAYERS [--dT 20] [--dir 1] [--step HEAT] [--frame -1]
                             [--area A] [--thickness L]

Method: the volume-weighted mean of the flux component HFL<dir> over an element set,
    q = sum(HFL_i * EVOL_i) / sum(EVOL_i)
For a set that spans the full thickness of a 1D-like slab this is the flux per unit area.
For 2D/3D details (studs, ties, thermal bridges), the volume average over the whole build-up
divided by dT gives the effective U including bridging. Needs HFL and EVOL in the field output.

  --dT    temperature difference between the two sink temperatures (Ti - Te); prints U = q/dT
  --area  if given, also prints the heat flow Q = q * area (W)
  --thickness  per-element-volume fallback when EVOL is missing (uniform mesh only)

Writes u_value.json next to the ODB. Transient steps: use --frame N, or average several frames yourself.

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


def opt(argv, key, default=None):
    if key in argv:
        i = argv.index(key)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def find_set(odb, name):
    name_u = name.upper()
    a = odb.rootAssembly
    for k in a.elementSets.keys():
        if k.upper() == name_u:
            return a.elementSets[k]
    for ik, inst in a.instances.items():
        for k in inst.elementSets.keys():
            if k.upper() == name_u:
                return inst.elementSets[k]
    raise KeyError('element set %s not found (assembly or instance level)' % name)


def main(argv):
    files = [a for a in argv if a.lower().endswith('.odb')]
    if not files or not opt(argv, '--set'):
        print(__doc__)
        return 2
    odb = openOdb(files[0], readOnly=True)
    sname = opt(argv, '--step') or list(odb.steps.keys())[-1]
    frame = odb.steps[sname].frames[int(opt(argv, '--frame', '-1'))]
    comp = int(opt(argv, '--dir', '1')) - 1
    es = find_set(odb, opt(argv, '--set'))
    hfl = frame.fieldOutputs['HFL'].getSubset(region=es, position=IP_POS)
    flux = {}
    for v in hfl.values:
        flux.setdefault((v.instance.name if v.instance else '', v.elementLabel), []).append(v.data[comp])
    vol = {}
    if 'EVOL' in frame.fieldOutputs.keys():
        for v in frame.fieldOutputs['EVOL'].getSubset(region=es).values:
            vol[(v.instance.name if v.instance else '', v.elementLabel)] = v.data
    if not vol:
        print('EVOL not in the field output: using equal weights (valid only for a uniform mesh)')
    num = den = 0.0
    for key, vals in flux.items():
        w = vol.get(key, 1.0)
        num += w * (sum(vals) / len(vals))
        den += w
    q = num / den if den else float('nan')
    res = dict(odb=os.path.basename(files[0]), step=sname, frame_time=frame.frameValue, set=opt(argv, '--set'),
               component='HFL%d' % (comp + 1), elements=len(flux), q_mean=q, weighted_by='EVOL' if vol else 'count')
    dT = opt(argv, '--dT')
    if dT:
        res['dT'] = float(dT)
        res['U'] = abs(q) / float(dT)
    if opt(argv, '--area'):
        res['Q'] = q * float(opt(argv, '--area'))
    odb.close()
    json.dump(res, open(os.path.splitext(files[0])[0] + '_u_value.json', 'w'), indent=2)
    for k in sorted(res):
        print('%-12s %s' % (k, res[k]))
    return 0


try:
    from abaqusConstants import INTEGRATION_POINT as IP_POS
except ImportError:          # allows a dry import outside Abaqus
    IP_POS = None

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
