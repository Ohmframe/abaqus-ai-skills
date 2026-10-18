---
name: abaqus-version-compat
description: Move Abaqus models, scripts and results between releases - rebuild a .cae for an older Abaqus version, upgrade old ODBs, and make scripts run on both the Python 2.7 (Abaqus 2023 and older) and Python 3.10 (2024 and newer) kernels. Use when someone cannot open a .cae or .odb because it was created by a newer release, needs a model saved for an older release, or a script fails after an Abaqus upgrade (print statements, f-strings, master/slave keyword errors).
---

# Abaqus version compatibility

> **Status: verified on Abaqus 2023 for the same-release round trip.** `export_for_older.py` ->
> `rebuild_from_inp.py` -> re-solve reproduces the cantilever exactly (-0.381909 mm, RF2 1000 N);
> `odb_upgrade.py --check` and `py23_check.py` behave as documented. The cross-release step (export in
> a newer release, rebuild in an older one) is not yet tested, so use the version matrix as guidance
> and confirm with a datacheck in the target release. See `TEST_REPORT.md`.

`.cae` and `.odb` files only go forward: a newer release opens an older file, never the reverse.
Anything going to an OLDER release must be rebuilt. Our rule at OhmFrame: every model is created by a
script, so "save it for 2021" means "run the script in 2021".

## When to use

* "This file was created by a newer version", or "make this `.cae` open in release X".
* An old ODB must be upgraded before a newer release can work with it.
* A script broke after an Abaqus upgrade, or must run on both 2.7 and 3.10 kernels.
* Not for: building the model in the first place (`abaqus-model-builder`).

## Files

| Path | Run with | Purpose |
|---|---|---|
| `scripts/export_for_older.py` | newer release: `abaqus cae noGUI=export_for_older.py -- model.cae out:dir [nogeom]` | `.inp` per model, SAT + STEP per part, a manifest with the keywords used and what each route loses |
| `scripts/rebuild_from_inp.py` | older release: `abaqus cae noGUI=rebuild_from_inp.py -- dir out:model_old.cae` | `mdb.ModelFromInputFile` per `.inp`; removes the empty `Model-1` only after a successful import; saves |
| `scripts/odb_upgrade.py` | `abaqus python odb_upgrade.py [--check] job.odb` | `isUpgradeRequiredForOdb` / `upgradeOdb` to `*_upg.odb`; never overwrites |
| `scripts/py23_check.py` | `python py23_check.py file_or_dir [--strict]` | Lints scripts for Python 2.7/3 and Abaqus API hazards (plain Python, no Abaqus needed) |

## Workflow

### A. "Make this model open in release X"

1. Find both releases: the user's, and the one that wrote the file (first lines of a `.dat`/`.msg`, or
   Help > About).
2. Build script available? Lint it with `py23_check.py`, fix the errors, run it in release X. Done.
3. No script: run `export_for_older.py` in the newer release, then `rebuild_from_inp.py` in release X.
   Tell the user that the parts become orphan meshes (no geometry, no feature tree). If the import
   complains, check the manifest's keyword list against release X's keyword documentation.
4. Geometry needed too: import the `.sat`/`.stp` (File > Import > Part) and re-apply properties, using
   the `.inp` as the reference. Better: write a build script now (`abaqus-model-builder`).
5. Run a datacheck in release X (`abaqus job=... datacheck interactive`) and compare a key result.

### B. "My script broke after upgrading Abaqus"

1. `python py23_check.py script.py`: fix ERRORs first (f-strings on 2.7; print statements and
   `except X, e` on 3), then WARNs.
2. `master=`/`slave=` became `main=`/`secondary=` in Abaqus 2022 (Tie, contact pairs, related
   constants and members). Use a try/except fallback, not a hard switch.
3. For a one-way 2 -> 3 migration, Abaqus 2024 and newer ship `abaqus python -m abqPy2to3`
   (check your release's documentation); re-lint afterwards. The result will no longer run on 2.7.
4. Restore builtins after `from abaqus import *` (it shadows `sum`, `min`, `max`, `abs`, `round`).

## Checks before you report

* The rebuilt model passes a datacheck in the target release.
* A key result (reaction sum, max displacement) from the target release matches the original release.
* `rebuild_log.json` / `export_manifest.json` show every model, part and step you expected.
* `py23_check.py` reports 0 errors for scripts that must run on both kernels.

## Rules

* Never overwrite the user's `.cae` or `.odb`; write new files.
* ODBs cannot go backwards: send CSV/JSON from `abaqus-odb-extract`, or re-run the job in the older release.
* Say explicitly what a route loses (geometry, feature tree, sets on geometry, display settings).

## References

* `references/version_matrix.md`: file compatibility, Python kernels by release, API renames, licensing.
* `examples/README.md`: taking the cantilever from `abaqus-model-builder` back to an older release.
* Related skills: `abaqus-model-builder`, `abaqus-odb-extract`.

## Background

Distilled from OhmFrame deliveries where a model had to open in an older release than the one it was
built in. Generic scripts only.
