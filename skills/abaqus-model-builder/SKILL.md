---
name: abaqus-model-builder
description: Build a native Abaqus/CAE model (.cae plus .inp) from a JSON spec with Abaqus Python (cae noGUI), run it in batch, and triage the .log/.sta/.msg/.dat files. Use when the user asks to create, script or automate an Abaqus model (parts, materials, sections, assembly, steps, contact/ties, BCs, loads, mesh, job), wants a .cae built "via the API/CLI" rather than clicked in the GUI, wants to run an Abaqus job from the command line, or needs to find out why a job failed or what its warnings mean.
---

# Abaqus model builder

You build Abaqus models as **scripts that generate a native `.cae`**: real parts, named sets and
surfaces, sections, steps and a job. Then you run them in batch and read the logs before you
trust any number. This is the workflow OhmFrame uses on client work. A script-built model can be
rebuilt in any release, diffed, reviewed and re-run, and opening the `.cae` still shows the full
model tree.

Requires a licensed Abaqus install (`abaqus` launcher). Nothing here has been verified against
every release. Check the results yourself.

## Files

- `scripts/build_from_spec.py`: the generic builder. Run it with `abaqus cae noGUI=... -- spec.json`.
- `scripts/validate_spec.py`: checks the spec in plain Python, with no Abaqus and no licence. Run it first.
- `scripts/run_job.sh`: build, then optional datacheck, then run, then log triage.
- `scripts/check_logs.py`: parses `.log/.sta/.msg/.dat`, groups errors and warnings, explains the known ones, exits non-zero on failure.
- `references/spec_schema.md`: every spec key.
- `references/api_cheatsheet.md`: the raw API calls, for anything the spec doesn't cover.
- `references/pitfalls.md`: 40 traps we hit on real projects. **Read it before you write custom code.**
- `examples/cantilever_beam.json` + `examples/README.md`: a worked case with the hand calculation.

## Workflow

1. **Pin down the spec with the user.** You need geometry, a unit system (say it explicitly, for
   example mm-N-tonne-s-MPa), materials, supports, loads, analysis type, outputs and acceptance
   checks. Write every assumption you make into the spec's `_comment` field and into your reply.
2. **Write the spec JSON.** Start from `examples/cantilever_beam.json`. Keep client data out of
   any file that will be shared.
   - Select regions with **bounding boxes** in global coordinates, never with `findAt` on guessed points.
   - Use one model per analysis type. Don't mix Standard and Explicit steps.
   - Apply point loads through an RP with a coupling, not to a single node.
3. **Validate offline:** `python scripts/validate_spec.py spec.json`. Fix every ERROR.
4. **Build:** `abaqus cae noGUI=scripts/build_from_spec.py -- spec.json`.
   - The build aborts on an empty selection or an unmeshed part. Fix the spec; don't hack around it.
   - Read the printed mesh Analysis Checks counts. If any are non-zero, use the `abaqus-mesh-doctor` skill.
   - The build writes `<job>.inp`, `<model>.cae` and `<job>_model.json` (counts, set sizes, steps).
5. **Datacheck first:** `abaqus job=<job>_check input=<job>.inp datacheck interactive`, then
   `python scripts/check_logs.py <job>_check`. Errors and unexpected warnings now cost seconds,
   not hours.
6. **Run:** `abaqus job=<job> input=<job>.inp cpus=N interactive ask_delete=OFF`, or `scripts/run_job.sh`.
   - Long runs: launch detached (`nohup`) and poll the `.sta`. A killed shell kills the solver.
   - Explicit runs over about 300k increments: add `double=both`.
   - Paths with spaces: pass `scratch=` with a path that has no spaces.
7. **Triage:** `python scripts/check_logs.py <job> --json <job>_logcheck.json`.
   - Exit code 0 means completed with no errors. Each warning group is still explained. Decide for
     each one whether it's expected (for example "will not be tied" with a tight tie tolerance) or a real problem.
   - Standard runs: look at cutbacks and the last step time. Explicit runs: look at the stable
     increment, % mass change and total-energy drift. Then use `abaqus-explicit-impact` for the full energy balance.
8. **Check the physics** before you report any number. Use a hand calculation (see the example),
   reaction-force equilibrium and the right deformed shape. Then extract results with the
   `abaqus-odb-extract` skill.
9. **Report** the results, the checks you ran, every assumption, and the warnings you accepted and why.

## Rules that save hours

- Write all Abaqus scripts so they run under Python 2.7 *and* 3. Restore `sum/min/max/abs/round`
  after `from abaqus import *`. Convert JSON strings with `to_str()`. Log to `sys.__stdout__`.
- Use `main=`/`secondary=` keywords (2022+). Fall back to `master=`/`slave=` on older releases.
  The `tie()` helper does this.
- Never edit `.jnl`/`.rpy` files and never read a `.cae` as text. Write a new script instead.
- When the user will open the `.cae`, keep sets, surfaces and model names meaningful. Name each
  model after its analysis. They will reuse your sets instead of re-picking them by hand, which
  would change the results.
- If the spec format can't express something, extend `build_from_spec.py` in the same style
  (one small function per feature, empty-selection guards) or write a dedicated builder that keeps
  all parameters at the top of the file. Never hard-code client values in a shared skill.

## Extending to other analyses

- Explicit impact or drop tests: see the `abaqus-explicit-impact` skill.
- Heat transfer and U-values: see `abaqus-heat-transfer`.
- Sheet-metal forming and FLD damage: see `abaqus-forming-fld`.
- Older-release deliverables: see `abaqus-version-compat`.
