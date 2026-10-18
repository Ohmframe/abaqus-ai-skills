---
name: abaqus-model-builder
description: Build a native Abaqus/CAE model (.cae plus .inp) from a JSON spec with Abaqus Python (abaqus cae noGUI), run it in batch, and triage the .log/.sta/.msg/.dat files. Use when the user asks to create, script or automate an Abaqus model (parts, materials, sections, assembly, steps, contact/ties, BCs, loads, mesh, job), wants a .cae built through the Python API or command line instead of the GUI, wants to run an Abaqus job from the command line, or needs to know why a job failed or what its warnings mean.
---

# Abaqus model builder

> **Status: untested.** The scripts and workflow in this skill have not been run in Abaqus yet.
> Treat every number they produce as unverified until the checks below pass, and tell the user so.

Build Abaqus models as **scripts that generate a native `.cae`**: real parts, named sets and surfaces,
sections, steps and a job. Then run them in batch and read the logs before you trust any number.
A script-built model can be rebuilt in any release, diffed, reviewed and re-run, and opening the
`.cae` still shows the full model tree. Requires a licensed Abaqus installation (`abaqus` launcher).

## When to use

* "Build / script / automate an Abaqus model of ..." (static, frequency, explicit or heat transfer).
* Run a job from the command line, do a datacheck, or launch a long run safely.
* "Why did my job abort?", "what does this warning mean?" (`.log`, `.sta`, `.msg`, `.dat`).
* Not for: mesh repair (`abaqus-mesh-doctor`), ODB post-processing (`abaqus-odb-extract`),
  older-release deliverables (`abaqus-version-compat`).

## Files

| Path | Run with | Purpose |
|---|---|---|
| `scripts/validate_spec.py` | `python validate_spec.py spec.json` | Checks a spec in plain Python (no Abaqus, no licence). Run it first. |
| `scripts/build_from_spec.py` | `abaqus cae noGUI=build_from_spec.py -- spec.json` | Generic builder: parts, partitions, materials, sections, mesh, instances, sets, surfaces, couplings, steps, BCs, loads, contact/ties, films, outputs, job; writes `.inp`, `.cae` and a model manifest |
| `scripts/run_job.sh` | `run_job.sh spec.json JOB [--cpus N] [--datacheck] [--double] [--no-run]` | Build, optional datacheck, run, log triage |
| `scripts/check_logs.py` | `python check_logs.py JOB [--dir RUN_DIR] [--json out.json]` | Parses `.log/.sta/.msg/.dat`, groups and explains errors and warnings, exits non-zero on failure |

## Workflow

1. **Pin down the spec with the user**: geometry, a unit system stated explicitly (for example
   mm-N-tonne-s-MPa), materials, supports, loads, analysis type, outputs and acceptance checks.
   Write every assumption into the spec's `_comment` field and into your reply.
2. **Write the spec JSON**, starting from `examples/cantilever_beam.json`. Keep the user's project
   data out of any file that will be shared.
   * Select regions with **bounding boxes** in global coordinates, never `findAt` on guessed points.
   * One model per analysis type; do not mix Standard and Explicit steps in one model.
   * Apply point loads through a reference point (RP) with a coupling, not to a single node.
3. **Validate offline**: `python scripts/validate_spec.py spec.json`. Fix every ERROR.
4. **Build**: `abaqus cae noGUI=scripts/build_from_spec.py -- spec.json`.
   * The build aborts on an empty selection or an unmeshed part. Fix the spec; do not hack around it.
   * Read the printed Analysis Checks counts. Non-zero counts: use `abaqus-mesh-doctor`.
   * Outputs: `<job>.inp`, `<model>.cae` and `<job>_model.json` (counts, set sizes, steps).
5. **Datacheck first**: `abaqus job=<job>_check input=<job>.inp datacheck interactive`, then
   `python scripts/check_logs.py <job>_check`. Set-up errors now cost seconds, not hours.
6. **Run**: `abaqus job=<job> input=<job>.inp cpus=N interactive ask_delete=OFF`, or `scripts/run_job.sh`.
   * Long runs: launch detached (`nohup ... &`) and poll the `.sta`. A killed shell kills the solver.
   * Explicit runs beyond about 300 000 increments: add `double=both`.
   * Paths with spaces: pass `scratch=` with a path that has no spaces.
7. **Triage**: `python scripts/check_logs.py <job> --json <job>_logcheck.json`. Exit code 0 means
   completed without errors; still decide for every warning group whether it is expected (for
   example "will not be tied" with a tight tie tolerance) or a real problem.
8. **Check the physics** (below), then extract results with `abaqus-odb-extract`.
9. **Report** results with units, the checks you ran, every assumption, the warnings you accepted and
   why, and that the scripts are untested.

## Checks before you report

* Hand calculation of the key quantity (beam theory, EA/L, 1D thermal resistance): same order of
  magnitude, ideally within a few percent for simple cases.
* Reaction equilibrium: summed reactions balance the applied loads.
* Deformed shape and load direction look right (sign errors show up here).
* Standard: no unexplained cutbacks; the last step reached its full time. Explicit: stable increment,
  % mass change and energy drift, then the full energy balance in `abaqus-explicit-impact`.

## Rules

* Scripts run on both Abaqus Python kernels: 2.7 (Abaqus 2023 and older) and 3.10 (2024 and newer).
  No f-strings; `from __future__ import print_function`; restore `sum/min/max/abs/round` after
  `from abaqus import *`; convert JSON strings with `to_str()`; log to `sys.__stdout__`.
* Contact and tie keywords: `main=`/`secondary=` from Abaqus 2022, `master=`/`slave=` before. Try the
  new keyword and fall back to the old one (the `tie()` helper does this).
* Never edit `.jnl`/`.rpy` files and never parse a `.cae` as text: write a new script instead.
* Never overwrite the user's `.cae`; save under a new name.
* Keep sets, surfaces and model names meaningful (name each model after its analysis) so the user
  reuses them instead of re-picking regions by hand, which changes results.
* If the spec cannot express something, extend `build_from_spec.py` in the same style (one small
  function per feature, empty-selection guards) or write a dedicated builder with all parameters at
  the top. Never hard-code project values in a shared skill.

## References

* `references/spec_schema.md`: every spec key.
* `references/api_cheatsheet.md`: the raw Abaqus Scripting Interface calls the builder makes, batch
  commands, and which job file to read for what.
* `references/pitfalls.md`: 40 traps. **Read it before writing custom code.**
* `examples/README.md`: steel cantilever with the hand calculation (δ ≈ 0.384 mm, RF2 = 1000 N).
* Related skills: `abaqus-odb-extract`, `abaqus-mesh-doctor`, `abaqus-explicit-impact`,
  `abaqus-heat-transfer`, `abaqus-forming-fld`, `abaqus-version-compat`.

## Background

Distilled from how OhmFrame builds Abaqus models on production work: every model is a script, every
job gets a datacheck and a log triage, and no number is reported without a hand check. Only the
generic method is included; the example is a textbook cantilever.
