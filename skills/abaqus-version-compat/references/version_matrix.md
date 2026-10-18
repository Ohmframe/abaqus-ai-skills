# Abaqus version matrix (what changes between releases that breaks scripts and files)

Abaqus releases are named by year (6.14 was the last numbered one, then 2016, 2017, ...).
Verify the details against the documentation of the releases you actually have.

## Files

| Item | Forward (old -> new) | Backward (new -> old) |
|---|---|---|
| `.cae` | opens, upgraded on save (keep a copy) | **no**. Rebuild: script, .inp import, or SAT/STEP |
| `.odb` | `abaqus upgrade -job new -odb old` or `odb_upgrade.py` | **no**. Re-run the job, or extract to CSV in the new release |
| `.inp` | usually fine (deprecated keywords warn) | works if every keyword exists in the old release |
| `.py` build script | fine if the API calls exist (see below) | best route; mind the Python version |
| `.sat` / `.stp` geometry | fine | fine (write the SAT with the version the old release reads if needed) |

## Python kernel

| Releases | Python | Consequences |
|---|---|---|
| up to 2023 | 2.7 | no f-strings, `print` needs `from __future__ import print_function`, str vs unicode |
| 2024 and newer | 3.10 | `print` statements, `except X, e`, `iteritems`, `xrange`, `has_key` fail |

Conversion helpers shipped with 2024+ (check the exact usage in your release's documentation):
`abaqus python -m abqPy2to3 <dir_or_file>` (2 -> 3 rewrite) and the `upgradeScript` utility for API
renames. They do not make a script run on 2.7
again; write the common subset (`py23_check.py` checks it).

## API renames we hit most

| Before | From release | Note |
|---|---|---|
| `master=`, `slave=` (Tie, contact pairs, couplings) | 2022: `main=`, `secondary=` | try the new keyword, fall back to the old (see build_from_spec.py `tie()`) |
| `MASTER`, `SLAVE` constants and `master`/`slave` members (for example general-contact surface assignments) | 2022: `MAIN`, `SECONDARY` and `main`/`secondary` names | same fallback; check the exact name in your release's Scripting Reference |
| `elemDeletion` / `maxDegradation` on `ElemType` | long-standing | check the keyword spelling in your release |
| `mdb.openStep` without `from caeModules import *` | all | import caeModules in noGUI scripts |

## Licensing note

* `abaqus cae noGUI=script.py` takes a CAE (pre/post) token.
* `abaqus python script.py` (odbAccess only) does not need a CAE token.
* Solver tokens scale with cores; check before submitting with `cpus=`.

## Checklist when someone says "I can't open your file"

1. Ask which release they run (`Help > About`, or the first lines of any .dat/.msg they made).
2. If we have the build script: run it in that release (or send it with instructions).
3. Else: `export_for_older.py` in our release -> send the export folder -> `rebuild_from_inp.py`
   in theirs. Tell them parts are orphan meshes.
4. Results: send CSV/plots from `abaqus-odb-extract`, not the ODB, unless they run the same or a newer release.
