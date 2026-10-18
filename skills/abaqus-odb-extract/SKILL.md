---
name: abaqus-odb-extract
description: Post-process Abaqus .odb result files with a generic, parameterised abaqus python script (no CAE licence token). Extracts field output (stress invariants and components, displacement, PEEQ, temperature, heat flux) with max/min and location, summed reaction forces over a set, history output for a node or RP set, whole-model energies with quasi-static and hourglass ratios, and de-duplicated contact forces, written to CSV plus summary.json. Use when the user has an .odb and wants numbers, curves, CSV/Excel-ready data, a results table, max stress, reaction force, force-displacement, an energy balance, or wants to know what an ODB contains.
---

# Abaqus ODB extract

> **Status: verified on Abaqus 2023.** `odb_probe.py` and `odb_extract.py` were run on Standard,
> Explicit and heat-transfer ODBs from the other skills' examples: field max/min with location,
> reaction sums, histories, energies and the graceful "no contact history" path all behaved as
> documented. Not yet run on any other release. See `TEST_REPORT.md`.

Get numbers out of an `.odb` with `abaqus python` (odbAccess; uses no CAE licence token) and write them
to CSV and JSON that any tool can read. The values the user quotes must come from the ODB itself,
not from screenshots of contour plots.

## When to use

* "What is the max Mises / displacement / PEEQ / temperature in this ODB?"
* Reaction force over a set, force-displacement curves, RP histories, energy histories.
* "What does this ODB contain?" (steps, frames, variables, sets).
* Contact forces from CFN history output.
* Not for: building or running models (`abaqus-model-builder`), FLD post-processing
  (`abaqus-forming-fld`), U-values (`abaqus-heat-transfer`), ODB upgrades (`abaqus-version-compat`).

## Files

| Path | Run with | Purpose |
|---|---|---|
| `scripts/odb_probe.py` | `abaqus python odb_probe.py Job.odb` | Lists steps, frames, field and history outputs, instances and sets. **Run it first.** |
| `scripts/odb_extract.py` | `abaqus python odb_extract.py Job.odb [options]` | The extractor: `--step`, `--field`, `--region`, `--frame`, `--reactions`, `--history-set`, `--history-var`, `--energies`, `--contact`, `--out` |

## Workflow

1. **Probe**: `abaqus python scripts/odb_probe.py Job.odb`. Confirm the step names, that the variables
   you need exist (an ODB only holds what was requested), and the exact set names. A missing variable
   means a new output request and a re-run; it cannot be extracted after the fact.
2. **Extract**:
   ```bash
   abaqus python scripts/odb_extract.py Job.odb --step Load \
       --field S:MISES --field U:MAGNITUDE --field PEEQ \
       --reactions FIXED_END --history-set RP_TIP --energies --contact --out Job_post
   ```
   * `--field VAR:COMP` takes an invariant (`MISES`, `MAGNITUDE`, `MAX_PRINCIPAL`, `TRESCA`, `PRESS`, ...)
     or a component (`S11`, `U2`, `HFL1`, ...). Add `--region INSTANCE_OR_SET` to restrict it.
   * `--frame all` writes one CSV per frame; the default is the last frame of the step.
   * `--reactions SET` sums RF/RM over the set for every frame (a reaction-vs-time curve).
3. **Check** (below) before you report anything.
4. **Report** values with units, the step/frame/time they come from, and integration-point vs nodal
   averaged values. Put the quantity and unit in file names, for example `S_MISES_MPa_max.csv`.

## Checks before you report

* **Equilibrium**: summed reactions balance the applied loads.
* **Order of magnitude**: compare with a hand calculation; investigate a 2x difference or more.
* **Peaks**: a single-element spike at a BC, load point or re-entrant corner is usually a singularity,
  not a design value. Say so, and quote the value one or two elements away or a linearised value.
* **Explicit**: `max_KE_over_IE_after_20pct` below 0.05-0.10 for a quasi-static claim, `AE_over_IE_end`
  below 0.05-0.10 (hourglass energy); a drifting `ETOTAL` is an energy-balance problem (see
  `abaqus-explicit-impact`).
* **Contact force**: use the de-duplicated series; summing every CFN output doubles the force.

## Rules

* Open ODBs read-only and never write to the user's ODB.
* ODB names are upper-case (`BEAM-1`, `RP_TIP`); the script looks them up case-insensitively.
* Shell and beam output has several section points; a plain max mixes top and bottom faces.
* Deleted elements keep their last values: keep only `STATUS` > 0.5 before taking a max
  (`odb_extract.py` does not filter them; `abaqus-forming-fld/scripts/fld_extract.py` does).
* Scripts run on Abaqus Python 2.7 and 3.10.

## References

* `references/odb_api.md`: the raw odbAccess calls and the traps (names, section points, history
  region names, duplicated contact output, bulk data access).
* `examples/README.md`: post-processing the cantilever from `abaqus-model-builder`, with hand values.
* To add a quantity (path plots, volume-weighted averages, HIC, dent depth), add one function in the
  style of `field_extract`, `reactions`, `history_dump`, `energies` or `contact_forces` and keep the CLI
  generic. For volume-weighted averages request `EVOL` and weight by it.

## Background

Distilled from OhmFrame's post-processing practice: numbers come from scripts, not screenshots, and
every table carries its units, frame and averaging. Generic code only; no project results are included.
