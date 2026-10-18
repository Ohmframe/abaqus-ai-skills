---
name: abaqus-version-compat
description: Move Abaqus models, scripts and results between releases - rebuild a .cae for an older Abaqus version, upgrade old ODBs, and make scripts run on both the Python 2.7 (<=2023) and Python 3 (2024+) kernels. Use when someone cannot open a .cae or .odb ("created by a newer version"), needs a model saved for an older release, or a script fails after an Abaqus upgrade (print/f-string/master-slave errors).
---

# Abaqus version compatibility

`.cae` and `.odb` files only go forward. Anything going to an OLDER release must be rebuilt.
OhmFrame's rule: every model is created by a script, so "save for 2021" means "run the
script in 2021".

## Scripts

| Script | Run with | Purpose |
|---|---|---|
| `scripts/export_for_older.py` | new release: `abaqus cae noGUI=export_for_older.py -- model.cae out:dir` | `.inp` per model, SAT+STEP per part, manifest with keywords and what each route loses |
| `scripts/rebuild_from_inp.py` | old release: `abaqus cae noGUI=rebuild_from_inp.py -- dir out:model_old.cae` | `ModelFromInputFile` per .inp, removes the empty Model-1 only after a successful import, saves |
| `scripts/odb_upgrade.py` | `abaqus python odb_upgrade.py [--check] job.odb` | `isUpgradeRequiredForOdb` / `upgradeOdb` to `*_upg.odb`, never overwrites |
| `scripts/py23_check.py` | plain `python py23_check.py file_or_dir` | lints scripts for Python 2.7/3 and Abaqus API hazards |

## Workflow: "make this model open in release X"

1. Find both releases (the user's, and the one that wrote the file: first lines of the .dat/.msg
   or File > Save As dialog).
2. Build script available? Lint it with `py23_check.py`, fix the errors, run it in release X. Done.
3. No script: `export_for_older.py` in the newer release, then `rebuild_from_inp.py` in release X.
   Tell the user parts become orphan meshes (no geometry edits); check the manifest's keyword list
   against release X's keyword manual if the import complains.
4. Geometry needed too: import the `.sat` (File > Import > Part) and re-apply properties, using the
   `.inp` as the reference. Better: write a build script now (`abaqus-model-builder`).
5. Run a data check in release X (`abaqus job=... datacheck interactive`) and compare a key result
   (reaction, max displacement) with the original.

## Workflow: "my script broke after upgrading Abaqus"

1. `python py23_check.py script.py`: fix ERRORs (f-strings on 2.7; print statements / `except X, e`
   on 3), then WARNs.
2. `master=`/`slave=` -> `main=`/`secondary=` from 2022: use a try/except fallback, not a hard switch.
3. For a pure 2 -> 3 migration Abaqus 2024+ ships `abaqus python -m abqPy2to3`; re-lint afterwards.
4. Restore builtins after `from abaqus import *` (it shadows `sum`, `min`, `max`, `abs`, `round`).

## Results

ODBs cannot go backwards. Send CSV/JSON from `abaqus-odb-extract`, or re-run the job in the older release.

Details: `references/version_matrix.md`. Worked example: `examples/README.md`.
Scripts untested on Abaqus by OhmFrame except where the README says otherwise.
