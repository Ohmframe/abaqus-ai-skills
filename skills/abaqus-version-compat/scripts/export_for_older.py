# -*- coding: utf-8 -*-
"""
export_for_older.py - run in the NEWER Abaqus release. Writes everything an OLDER release needs
to rebuild a .cae it cannot open (a .cae is only forward compatible: 2024 opens a 2021 file,
never the reverse).

    abaqus cae noGUI=export_for_older.py -- model.cae [out:export_dir] [models:M1,M2] [nogeom]

Per model:
  <out>/<model>.inp           complete input deck (orphan mesh + materials, steps, loads, ...)
Per part with geometry (skip with 'nogeom'):
  <out>/<model>__<part>.sat   ACIS geometry   (writeAcisFile; opens in the older release)
  <out>/<model>__<part>.stp   STEP geometry   (writeStepFile; any CAD tool)
Plus:
  <out>/export_manifest.json  release used, models, parts, steps, interactions, keywords found
                              in each .inp, and what will be LOST by each route.

Then in the older release:   abaqus cae noGUI=rebuild_from_inp.py -- <out>  [out:model_old.cae]

Routes, best first (see references/version_matrix.md):
  1. the model was built by a script -> just run that script in the older release (native
     geometry, features, sets: nothing lost). This is why OhmFrame builds every model by script.
  2. .inp import -> exact analysis model, but parts become orphan meshes (no geometry/features).
  3. .sat/.stp + a rebuild script -> geometry back, but materials/steps/loads must be re-applied
     (the .inp from step 2 is the reference for those).

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
try:
    import builtins as _bi
except ImportError:
    import __builtin__ as _bi
sum, min, max, round, abs = _bi.sum, _bi.min, _bi.max, _bi.round, _bi.abs


def log(s):
    sys.__stdout__.write(str(s) + '\n')
    sys.__stdout__.flush()


def arg(key, default=None):
    for a in sys.argv:
        if a.startswith(key + ':') or a.startswith(key + '='):
            return a[len(key) + 1:]
    return default


cae = [a for a in sys.argv if a.lower().endswith('.cae')]
if not cae:
    raise SystemExit(__doc__)
CAE = cae[-1]
OUT = arg('out', os.path.splitext(os.path.basename(CAE))[0] + '_export')
ONLY = arg('models')
NOGEOM = 'nogeom' in sys.argv
if not os.path.isdir(OUT):
    os.makedirs(OUT)
openMdb(pathName=CAE)


def safe(s):
    return re.sub(r'[^A-Za-z0-9_\-]+', '_', s)


manifest = dict(source=os.path.basename(CAE), release=str(globals().get('version', 'unknown')),
                models=[])
names = ONLY.split(',') if ONLY else list(mdb.models.keys())
for mname in names:
    m = mdb.models[mname]
    entry = dict(name=mname, parts=[], steps=[s for s in m.steps.keys() if s != 'Initial'],
                 materials=list(m.materials.keys()), interactions=list(m.interactions.keys()),
                 constraints=list(m.constraints.keys()), problems=[])
    # 1. input deck (needs instances; an empty assembly writes an empty deck)
    if len(m.rootAssembly.instances) == 0:
        entry['problems'].append('assembly has no instances: .inp will contain no mesh')
    jname = 'EXP_' + safe(mname)[:30]
    try:
        j = mdb.Job(name=jname, model=mname)
        j.writeInput(consistencyChecking=OFF)
        dst = os.path.join(OUT, safe(mname) + '.inp')
        if os.path.exists(dst):
            os.remove(dst)
        os.rename(jname + '.inp', dst)
        del mdb.jobs[jname]
        txt = open(dst).read()
        kws = sorted(set(k.upper() for k in re.findall(r'^\*([A-Za-z][A-Za-z ]*?)\s*(?:,|$)', txt, re.M)))
        entry['inp'] = os.path.basename(dst)
        entry['keywords'] = kws
        log('model %s -> %s (%d keywords)' % (mname, dst, len(kws)))
    except Exception as exc:
        entry['problems'].append('writeInput failed: %s' % exc)
        log('model %s: writeInput FAILED: %s' % (mname, exc))
    # 2. geometry per part
    for pname, p in m.parts.items():
        pe = dict(name=pname, cells=len(p.cells), faces=len(p.faces), elements=len(p.elements),
                  orphan_mesh=(len(p.faces) == 0 and len(p.elements) > 0))
        if not NOGEOM and len(p.faces) > 0:
            base = os.path.join(OUT, '%s__%s' % (safe(mname), safe(pname)))
            for ext, fn in (('.sat', 'writeAcisFile'), ('.stp', 'writeStepFile')):
                try:
                    getattr(p, fn)(base + ext)
                    pe.setdefault('files', []).append(os.path.basename(base + ext))
                except Exception as exc:
                    pe.setdefault('export_errors', []).append('%s: %s' % (fn, exc))
        entry['parts'].append(pe)
    manifest['models'].append(entry)

manifest['lost_by_route'] = {
    'inp_import': ['part geometry and feature history (parts become orphan meshes)',
                   'sketches, partitions, datums, mesh controls/seeds',
                   'geometry-based sets become node/element sets', 'display settings, views, XY data'],
    'sat_step_geometry': ['features, partitions (re-create), mesh', 'all materials, sections, steps, loads, '
                          'interactions (re-apply; use the .inp as the reference)'],
}
manifest['next_step'] = 'older release: abaqus cae noGUI=rebuild_from_inp.py -- %s' % OUT
json.dump(manifest, open(os.path.join(OUT, 'export_manifest.json'), 'w'), indent=2)
log('wrote %s' % os.path.join(OUT, 'export_manifest.json'))
