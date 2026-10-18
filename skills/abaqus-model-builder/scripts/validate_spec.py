#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
validate_spec.py - check a build_from_spec.py JSON spec WITHOUT Abaqus.

    python validate_spec.py spec.json

Catches the cheap mistakes before a CAE licence token is spent: unknown types, references
to parts/sets/surfaces/steps/materials/sections that do not exist, bounding boxes with
min > max, BCs that set values in the Initial step, missing mesh blocks, heat steps
without conductivity, explicit steps without density. Plain Python 2.7 or 3.

OhmFrame - https://ohmframe.com - MIT licence.
"""
from __future__ import print_function

import json
import sys

PART_TYPES = ('box', 'rect_shell', 'plate_with_hole', 'cylinder', 'polygon', 'step')
STEP_TYPES = ('static', 'frequency', 'explicit', 'heat_steady', 'heat_transient')
BC_TYPES = ('encastre', 'pinned', 'xsymm', 'ysymm', 'zsymm', 'displacement', 'velocity', 'temperature')
LOAD_TYPES = ('concentrated_force', 'pressure', 'gravity', 'surface_heat_flux')
INTER_TYPES = ('tie', 'general_contact', 'general_contact_explicit', 'film')


def validate(spec):
    errs, warns = [], []
    E, W = errs.append, warns.append
    for key in ('model_name', 'parts', 'instances', 'steps'):
        if key not in spec:
            E('missing top-level key "%s"' % key)
    if errs:
        return errs, warns
    parts = dict((p['name'], p) for p in spec['parts'])
    mats = dict((m['name'], m) for m in spec.get('materials', []))
    secs = dict((s['name'], s) for s in spec.get('sections', []))
    insts = dict((i['name'], i) for i in spec['instances'])
    steps = [s['name'] for s in spec['steps']]
    sets = set(r['name'] for r in spec.get('reference_points', []))
    surfs = set()
    for p in spec['parts']:
        if p.get('type') not in PART_TYPES:
            E('part %s: unknown type %s' % (p.get('name'), p.get('type')))
    for s in spec.get('sections', []):
        if s.get('material') not in mats:
            E('section %s uses unknown material %s' % (s['name'], s.get('material')))
        if s.get('type') == 'shell' and 'thickness' not in s:
            E('shell section %s has no thickness' % s['name'])
    assigned = set()
    for sa in spec.get('section_assignments', []):
        if sa['part'] not in parts:
            E('section assignment to unknown part %s' % sa['part'])
        if sa['section'] not in secs:
            E('section assignment uses unknown section %s' % sa['section'])
        assigned.add(sa['part'])
    for p in parts:
        if p not in assigned:
            W('part %s has no section assignment (fine only for rigid/reference parts)' % p)
    meshed = set(m['part'] for m in spec.get('mesh', []))
    for p in parts:
        if p not in meshed:
            W('part %s has no mesh block' % p)
    for i in spec['instances']:
        if i['part'] not in parts:
            E('instance %s uses unknown part %s' % (i['name'], i['part']))
    for group, store in (('sets', sets), ('surfaces', surfs)):
        for s in spec.get(group, []):
            if s.get('instance') not in insts:
                E('%s %s: unknown instance %s' % (group, s['name'], s.get('instance')))
            b = s.get('bbox', [])
            if len(b) != 6 or any(b[k] > b[k + 3] for k in range(3)):
                E('%s %s: bbox must be [xmin,ymin,zmin,xmax,ymax,zmax] with min <= max' % (group, s['name']))
            if s['name'] in sets or s['name'] in surfs:
                E('name %s used twice' % s['name'])
            store.add(s['name'])
            if s['name'].upper() in [n.upper() for n in insts]:
                E('set/surface %s has the same name as an instance' % s['name'])
    regions = sets | surfs
    for c in spec.get('couplings', []):
        if c['control'] not in sets:
            E('coupling %s: control point set %s not defined' % (c['name'], c['control']))
        if c['surface'] not in regions:
            E('coupling %s: surface/set %s not defined' % (c['name'], c['surface']))
    for s in spec['steps']:
        if s.get('type') not in STEP_TYPES:
            E('step %s: unknown type %s' % (s.get('name'), s.get('type')))
        if s.get('type') == 'explicit':
            if 'time_period' not in s:
                E('explicit step %s needs time_period' % s['name'])
            for m in mats.values():
                if 'density' not in m:
                    E('explicit analysis: material %s has no density' % m['name'])
        if s.get('type', '').startswith('heat'):
            for m in mats.values():
                if 'conductivity' not in m:
                    E('heat transfer: material %s has no conductivity' % m['name'])
                if s['type'] == 'heat_transient' and ('density' not in m or 'specific_heat' not in m):
                    E('transient heat: material %s needs density and specific_heat' % m['name'])
    kinds = set(s.get('type') for s in spec['steps'])
    if 'explicit' in kinds and kinds & set(('static', 'frequency', 'heat_steady', 'heat_transient')):
        E('explicit and standard steps in one model: split into two models/jobs')
    allowed_steps = set(['Initial'] + steps)
    for b in spec.get('bcs', []):
        if b.get('type') not in BC_TYPES:
            E('bc %s: unknown type %s' % (b.get('name'), b.get('type')))
        if b.get('set') not in regions:
            E('bc %s: set %s not defined' % (b['name'], b.get('set')))
        if b.get('step', 'Initial') not in allowed_steps:
            E('bc %s: unknown step %s' % (b['name'], b.get('step')))
        if b.get('step', 'Initial') == 'Initial' and any(
                b.get(d, 0) not in (0, 0.0) for d in ('u1', 'u2', 'u3', 'ur1', 'ur2', 'ur3')):
            E('bc %s: non-zero prescribed value in the Initial step; create it in an analysis step' % b['name'])
    for ld in spec.get('loads', []):
        if ld.get('type') not in LOAD_TYPES:
            E('load %s: unknown type %s' % (ld.get('name'), ld.get('type')))
        if ld.get('step') not in steps:
            E('load %s: unknown step %s' % (ld['name'], ld.get('step')))
        ref = ld.get('set') or ld.get('surface')
        if ld['type'] != 'gravity' and ref not in regions:
            E('load %s: region %s not defined' % (ld['name'], ref))
        if ld['type'] in ('pressure', 'surface_heat_flux') and ld.get('surface') not in surfs:
            E('load %s: needs a surface (not a set)' % ld['name'])
    for it in spec.get('interactions', []):
        if it.get('type') not in INTER_TYPES:
            E('interaction %s: unknown type %s' % (it.get('name'), it.get('type')))
        for k in ('main', 'secondary', 'surface'):
            if k in it and it[k] not in regions:
                E('interaction %s: %s region %s not defined' % (it['name'], k, it[k]))
        if it.get('type') == 'tie' and it.get('adjust'):
            W('tie %s: adjust=true moves secondary nodes onto the main surface; on faceted or curved '
              'surfaces this can distort elements' % it['name'])
    for h in spec.get('outputs', {}).get('history', []):
        if h.get('set') not in sets:
            E('history output %s: set %s not defined (history needs a set, not a surface)'
              % (h['name'], h.get('set')))
    return errs, warns


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    spec = json.load(open(argv[1]))
    errs, warns = validate(spec)
    for w in warns:
        print('WARNING: ' + w)
    for e in errs:
        print('ERROR:   ' + e)
    print('%s: %d error(s), %d warning(s)' % (argv[1], len(errs), len(warns)))
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
