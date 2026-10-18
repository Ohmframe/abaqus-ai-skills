---
name: abaqus-odb-extract
description: Post-process Abaqus .odb result files with a generic, parameterised abaqus python script. Gets field outputs (stress invariants/components, displacement, PEEQ, temperature, heat flux) with max/min and their location, summed reaction forces over a set, history outputs for a node or RP set, whole-model energies with quasi-static/hourglass ratios, and de-duplicated contact forces, all written to CSV plus a summary.json. Use when the user has an .odb and wants numbers, curves, CSV/Excel-ready data, a results table, max stress, reaction force, force-displacement, energy balance, or wants to know what an ODB contains.
---

# Abaqus ODB extract

You get numbers out of an `.odb` with `abaqus python`, which uses no CAE licence token, and you
write them to CSV and JSON that any tool can read. The results the user quotes must come
from the ODB itself, not from screenshots.

## Files

- `scripts/odb_probe.py`: lists steps, frames, field and history outputs, instances and sets. **Run it first.**
- `scripts/odb_extract.py`: the extractor. It takes `--field`, `--reactions`, `--history-set`, `--energies` and `--contact`.
- `references/odb_api.md`: the raw API, and the traps (upper-case names, section points, duplicated contact output).
- `examples/README.md`: post-processing the cantilever from `abaqus-model-builder`, with expected values.

## Workflow

1. **Probe:** `abaqus python scripts/odb_probe.py Job.odb`. Confirm the step names, that the
   variables you need exist (an ODB only contains what was requested), and the exact set names.
   If a variable is missing, the fix is a new output request and a re-run. You can't extract it
   after the fact.
2. **Extract:**
   ```bash
   abaqus python scripts/odb_extract.py Job.odb --step Load \
       --field S:MISES --field U:MAGNITUDE --field PEEQ \
       --reactions FIXED_END --history-set RP_TIP --energies --contact --out Job_post
   ```
   - `--field VAR:COMP` takes an invariant (`MISES`, `MAGNITUDE`, `MAX_PRINCIPAL`, `TRESCA`, `PRESS`, ...)
     or a component (`S11`, `U2`, `HFL1`, ...). Add `--region INSTANCE_OR_SET` to restrict it.
   - `--frame all` writes one CSV per frame. The default is the last frame.
   - `--reactions SET` sums RF/RM over the set for every frame. That gives a reaction-vs-time curve.
3. **Sanity-check before reporting:**
   - **Equilibrium:** the summed reactions must balance the applied loads.
   - **Order of magnitude:** compare against a hand calculation. Stop and investigate if they're off by 2x or more.
   - **Peaks:** a single-element stress spike at a BC, load point or re-entrant corner is usually a
     singularity, not a design value. Report it as such, and quote the value one or two elements away
     or a linearised value.
   - **Explicit:** `max_KE_over_IE_after_20pct` < 0.05-0.10 for a quasi-static claim, and `AE_over_IE_end`
     < 0.05-0.10 (hourglass energy). A drifting `ETOTAL` means an energy-balance problem
     (see `abaqus-explicit-impact`).
   - **Contact force:** use the de-duplicated series. Raw sums of every CFN output double the force.
4. **Report** values with units, the step/frame/time they come from, and integration-point vs nodal
   averaging. Put the quantity and unit in file names, for example `S_MISES_MPa_max.csv`.

## Extending

Each extraction is a small function in `odb_extract.py` (`field_extract`, `reactions`,
`history_dump`, `energies`, `contact_forces`). For a project-specific quantity (path plots,
volume-weighted averages, HIC, dent depth), add a function in the same style and keep the CLI
generic. For volume-weighted averages, request `EVOL` and weight by it (see `abaqus-heat-transfer`).
