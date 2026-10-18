# -*- coding: utf-8 -*-
"""
rebuild_from_inp.py - run in the OLDER Abaqus release. Imports one or more .inp files (for
example the output of export_for_older.py) as models and saves a .cae native to this release.

    abaqus cae noGUI=rebuild_from_inp.py -- export_dir          [out:model_rebuilt.cae]
    abaqus cae noGUI=rebuild_from_inp.py -- a.inp b.inp         [out:model_rebuilt.cae]

  * one model per .inp, named after the file
  * the default empty 'Model-1' is deleted only AFTER at least one import succeeded
    (deleting the last model first raises an error)
  * keywords the older release does not know make the import fail or skip lines: the list of
    keywords is in export_manifest.json, check them against this release's keyword manual
  * the result is an orphan-mesh model: geometry edits need the .sat/.stp route

Writes rebuild_log.json with per-file status, part/step/material counts.

Python 2.7 and 3.  OhmFrame - https://ohmframe.com - MIT licence.
"""
from __future__ import print_function

import glob
import json
import os
import re
import sys

from abaqus import *
from abaqusConstants import *
from caeModules import *
try:
    import builtins as _bi
except ImportError:
    import __builtin__ as _bi
sum, min, max, round, abs = _bi.sum, _bi.min, _bi.max, _bi.round, _bi.abs


def log(s):
    sys.__stdout__.write(str(s) + '\n')
    sys.__stdout__.flush()


args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
OUT = 'model_rebuilt.cae'
inps = []
for a in args:
    if a.startswith('out:') or a.startswith('out='):
        OUT = a[4:]
    elif os.path.isdir(a):
        inps += sorted(glob.glob(os.path.join(a, '*.inp')))
    elif a.lower().endswith('.inp'):
        inps.append(a)
if not inps:
    raise SystemExit(__doc__)

report, ok = [], 0
for f in inps:
    name = re.sub(r'[^A-Za-z0-9_\-]+', '_', os.path.splitext(os.path.basename(f))[0])[:38]
    if name in mdb.models.keys():
        name += '_inp'
    try:
        mdb.ModelFromInputFile(name=name, inputFileName=f)
        m = mdb.models[name]
        r = dict(file=f, model=name, status='ok', parts=len(m.parts),
                 instances=len(m.rootAssembly.instances), materials=len(m.materials),
                 steps=[s for s in m.steps.keys() if s != 'Initial'])
        ok += 1
    except Exception as exc:
        r = dict(file=f, model=name, status='FAILED', error=str(exc))
    report.append(r)
    log('%-40s %s' % (os.path.basename(f), r['status'] + ('' if r['status'] == 'ok' else ': ' + r['error'])))

if ok and 'Model-1' in mdb.models.keys() and len(mdb.models) > 1:
    del mdb.models['Model-1']
if ok:
    mdb.saveAs(pathName=OUT)
    log('saved %s (%d model(s)) in release %s' % (OUT, ok, globals().get('version', '?')))
else:
    log('no model imported - nothing saved')
json.dump(dict(release=str(globals().get('version', '?')), saved=OUT if ok else None, files=report),
          open('rebuild_log.json', 'w'), indent=2)
sys.exit(0 if ok == len(inps) else 1)
