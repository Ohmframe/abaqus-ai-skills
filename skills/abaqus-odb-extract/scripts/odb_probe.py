# -*- coding: utf-8 -*-
"""
odb_probe.py - list what is inside an ODB before you extract anything (run with abaqus python).

    abaqus python odb_probe.py JOB.odb [--json probe.json]

Prints the release, steps (time period, frame count), field outputs per step (last frame,
with type, positions, components and invariants), history regions with their outputs,
instances (node/element counts, element types) and assembly/instance sets. Read-only.

OhmFrame - https://ohmframe.com - MIT licence.
"""
from __future__ import print_function

import json
import sys

from odbAccess import openOdb, isUpgradeRequiredForOdb


def main(argv):
    path = [a for a in argv[1:] if a.lower().endswith('.odb')]
    if not path:
        raise SystemExit(__doc__)
    path = path[0]
    if isUpgradeRequiredForOdb(upgradeRequiredOdbPath=path):
        raise SystemExit('%s was written by an older release: upgrade a copy first '
                         '(abaqus-version-compat/scripts/odb_upgrade.py)' % path)
    odb = openOdb(path=path, readOnly=True)
    rep = dict(odb=path, steps={}, instances={}, assembly_sets={})
    try:
        for sname, st in odb.steps.items():
            s = dict(procedure=str(st.procedure), time_period=st.timePeriod, frames=len(st.frames),
                     fields={}, history={})
            if len(st.frames):
                fr = st.frames[-1]
                for k, fo in fr.fieldOutputs.items():
                    s['fields'][k] = dict(type=str(fo.type), description=fo.description,
                                          components=[str(c) for c in fo.componentLabels],
                                          invariants=[str(c) for c in fo.validInvariants],
                                          positions=sorted(set(str(l.position) for l in fo.locations)))
            for rn, reg in st.historyRegions.items():
                s['history'][rn] = sorted(reg.historyOutputs.keys())
            rep['steps'][sname] = s
        for iname, inst in odb.rootAssembly.instances.items():
            types = {}
            for e in inst.elements:
                types[e.type] = types.get(e.type, 0) + 1
            rep['instances'][iname] = dict(nodes=len(inst.nodes), elements=len(inst.elements),
                                           element_types=types, node_sets=sorted(inst.nodeSets.keys()),
                                           element_sets=sorted(inst.elementSets.keys()))
        ra = odb.rootAssembly
        rep['assembly_sets'] = dict(node_sets=sorted(ra.nodeSets.keys()),
                                    element_sets=sorted(ra.elementSets.keys()),
                                    surfaces=sorted(ra.surfaces.keys()))
    finally:
        odb.close()

    for sname, s in rep['steps'].items():
        print('STEP %s  %s  T=%g  frames=%d' % (sname, s['procedure'], s['time_period'], s['frames']))
        for k, f in sorted(s['fields'].items()):
            print('   field %-10s %-16s %s comps=%s inv=%s' % (k, f['type'], f['positions'], f['components'],
                                                             f['invariants']))
        for rn, outs in sorted(s['history'].items()):
            shown = ', '.join(outs[:12]) + (' ...' if len(outs) > 12 else '')
            print('   history %-34s %s' % (rn, shown))
    for iname, i in sorted(rep['instances'].items()):
        print('INSTANCE %s  nodes %d  elements %d  %s' % (iname, i['nodes'], i['elements'], i['element_types']))
        print('   node sets: %s' % i['node_sets'])
    print('ASSEMBLY node sets: %s' % rep['assembly_sets']['node_sets'])
    print('ASSEMBLY element sets: %s' % rep['assembly_sets']['element_sets'])
    if '--json' in argv:
        with open(argv[argv.index('--json') + 1], 'w') as fh:
            json.dump(rep, fh, indent=2, sort_keys=True)


if __name__ == '__main__':
    main(sys.argv)
