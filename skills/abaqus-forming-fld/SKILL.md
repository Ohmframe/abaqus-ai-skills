---
name: abaqus-forming-fld
description: Sheet-metal forming limit analysis in Abaqus/Explicit - Nakajima-type hemispherical punch stretch models, FLD damage initiation (FldDamageInitiation), damage evolution and element deletion, and extraction of necking onset, limit dome height and major/minor strain points for the forming limit diagram. Use when the user asks about forming limits, FLD/FLC, necking or splitting prediction in sheet forming, or post-processing FLDCRT from an ODB.
---

# Abaqus forming limit (FLD)

OhmFrame workflow for predicting necking in sheet forming with the FLD criterion.

## Scripts

| Script | Run with | Purpose |
|---|---|---|
| `scripts/build_dome_stretch.py` | `abaqus cae noGUI=build_dome_stretch.py [-- submit]` | Quarter-blank hemispherical punch stretch (full disc or strip of width `STRIP_WIDTH`), power-law hardening, FLC table, energy damage evolution, element deletion, smooth-step stroke, optional mass scaling |
| `scripts/fld_extract.py` | `abaqus python fld_extract.py job.odb --rp-set RP_PUNCH` | Per-frame max FLDCRT, elements over 1, deleted elements, punch stroke/force; onset and fracture frames; major/minor strains at onset for the FLD plot |
| `../abaqus-explicit-impact/scripts/energy_balance.py` | `--mode quasistatic` | prove the explicit run is quasi-static |

## Workflow

1. Get the sheet data: thickness, hardening curve to large strain, FLC (true strain), friction, test
   geometry (punch radius, die/flange). No FLC = no FLD answer; say so instead of guessing.
2. Build (template or `abaqus-model-builder`), replacing the illustrative material and FLC.
3. Run a coarse quick model first; check the quasi-static energy ratios, then refine the dome mesh.
4. `fld_extract.py`: onset frame/stroke (= predicted limit dome height), failure location, strain points.
5. Validate against the test (dome height, failure location) before using the model for parts.
   Report onset (FLDCRT = 1) as the answer; post-onset deletion is mesh dependent.

Background and checklist: `references/fld_notes.md`. Example: `examples/README.md`.

## Lessons behind this skill
From an OhmFrame study reproducing published forming-limit tests with FLD damage and element deletion.
Only the generic method is included: the template uses a Nakajima-style dome with illustrative values, not
the study's geometry, material or data. This skill has the thinnest source base of the set
(one project); treat it as a starting point. Scripts untested on Abaqus by OhmFrame.
