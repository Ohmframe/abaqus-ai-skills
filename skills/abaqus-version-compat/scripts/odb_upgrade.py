# -*- coding: utf-8 -*-
"""
odb_upgrade.py - check and upgrade output databases written by an OLDER Abaqus release so the
current release can open them. Runs with the plain Abaqus Python (no CAE licence):

    abaqus python odb_upgrade.py job.odb [more.odb ...]        # check + upgrade -> job_upg.odb
    abaqus python odb_upgrade.py --check job.odb               # only report

The original file is never overwritten.

Note the direction: ODBs, like .cae files, only go FORWARD. An older release cannot read an
ODB from a newer one. To get results into an older release either re-run the job there
(rebuild the model with export_for_older.py / rebuild_from_inp.py) or extract the numbers
in the new release with abaqus-odb-extract (CSV/JSON open anywhere).

Python 2.7 and 3.  OhmFrame - https://ohmframe.com - MIT licence.
"""
from __future__ import print_function

import os
import sys

from odbAccess import isUpgradeRequiredForOdb, upgradeOdb, openOdb


def main(argv):
    check_only = '--check' in argv
    files = [a for a in argv if not a.startswith('--')]
    if not files:
        print(__doc__)
        return 2
    rc = 0
    for f in files:
        if not os.path.exists(f):
            print('%s: not found' % f)
            rc = 1
            continue
        try:
            need = isUpgradeRequiredForOdb(upgradeRequiredOdbPath=f)
        except Exception as exc:
            print('%s: cannot check (%s) - possibly written by a NEWER release or corrupt' % (f, exc))
            rc = 1
            continue
        if not need:
            try:
                o = openOdb(f, readOnly=True)
                print('%s: current format, steps=%s' % (f, list(o.steps.keys())))
                o.close()
            except Exception as exc:
                print('%s: current format but failed to open: %s' % (f, exc))
                rc = 1
            continue
        if check_only:
            print('%s: UPGRADE REQUIRED' % f)
            continue
        dst = os.path.splitext(f)[0] + '_upg.odb'
        try:
            upgradeOdb(existingOdbPath=f, upgradedOdbPath=dst)
            print('%s: upgraded -> %s' % (f, dst))
        except Exception as exc:
            print('%s: upgrade FAILED: %s' % (f, exc))
            rc = 1
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
