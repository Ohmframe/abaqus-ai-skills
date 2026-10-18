---
name: abaqus-forming-fld
description: Sheet-metal forming limit analysis in Abaqus/Explicit - Nakajima-type hemispherical punch stretch models, FLD damage initiation (FldDamageInitiation), damage evolution and element deletion, and extraction of necking onset, limit dome height and major/minor strain points for the forming limit diagram. Use when the user asks about forming limits, FLD or FLC, necking or splitting prediction in sheet forming, dome-stretch simulations, or post-processing FLDCRT from an ODB.
---

# Abaqus forming limit (FLD)

> **Status: verified on Abaqus 2023 (mechanics and post-processing).** The dome-stretch example reaches
> necking onset at 53.7 mm of a 70 mm stroke with the punch force collapsing from 15.6 kN, the
> strain-path series moves from biaxial toward plane strain as documented, and the quasi-static check
> passes (KE/IE 0.145 %). The default material and FLC are illustrative and the onset is from a single
> mesh: a forming limit for a real sheet needs measured data and test comparison, so tell the user.
> Abaqus 2024+ is not yet tested. See `TEST_REPORT.md`.

Necking prediction in sheet forming with the forming limit diagram (FLD) damage initiation criterion
in Abaqus/Explicit.

## When to use

* Forming limit questions: FLD/FLC, necking or splitting onset, limit dome height.
* Nakajima-type hemispherical punch stretch models on discs or strips of different widths.
* Post-processing FLDCRT, major/minor strain points and element deletion from an ODB.
* Not for: crash or impact (`abaqus-explicit-impact`), general explicit set-up (`abaqus-model-builder`).

## Files

| Path | Run with | Purpose |
|---|---|---|
| `scripts/build_dome_stretch.py` | `abaqus cae noGUI=build_dome_stretch.py [-- submit]` | Quarter-blank hemispherical punch stretch (full disc, or a strip of width `STRIP_WIDTH`), power-law hardening, FLC table, energy-based damage evolution, element deletion, smooth-step stroke, optional mass scaling |
| `scripts/fld_extract.py` | `abaqus python fld_extract.py job.odb --rp-set RP_PUNCH [--set S] [--step S] [--frame F] [--out DIR]` | Per-frame max FLDCRT, elements over 1, deleted elements, punch stroke and force; onset and fracture frames; major/minor strains at onset for the FLD plot |
| `../abaqus-explicit-impact/scripts/energy_balance.py` | `abaqus python energy_balance.py job.odb --mode quasistatic` | Shows whether the explicit run is quasi-static |

## Workflow

1. **Get the sheet data**: thickness, hardening curve to large strain, FLC in true (logarithmic) strain,
   friction, test geometry (punch radius, die and flange). No FLC means no FLD answer: say so instead
   of guessing.
2. **Build** (template or `abaqus-model-builder`), replacing the illustrative material and FLC.
   Units: mm-tonne-s-N-MPa.
3. **Run a coarse model first**; check the quasi-static energy ratios, then refine the dome mesh.
4. **Extract** with `fld_extract.py`: onset frame and stroke (the predicted limit dome height), failure
   location, strain points.
5. **Compare with tests** (dome height, failure location) before the model is used for parts. Report
   onset (FLDCRT = 1) as the answer; post-onset element deletion is mesh dependent.

## Checks before you report

* Quasi-static: ALLKE/ALLIE below 5-10 % (`energy_balance.py --mode quasistatic`), DMASS small.
* Initial yield printed by the build script matches K·ε0ⁿ from the hardening law.
* Strain path at the failure point looks right for the specimen (full disc ≈ equi-biaxial; narrow
  strips toward uniaxial).
* Results reported at onset (FLDCRT = 1), with the mesh size in the dome region stated.

## Rules

* The FLD criterion applies to plane-stress formulations (shells such as S4R/S3R, membranes); use
  5 or more section points and a seed of about 1-2 x the sheet thickness in the dome region.
* `FldDamageInitiation(table=((major, minor), ...))` takes the FLC as (major, minor) pairs in true
  strain, the same convention as LE.
* The FLC is valid for (near) linear strain paths. For strongly non-linear paths consider a
  stress-based limit (FLSD, `FlsdDamageInitiation`) or MSFLD, and say why.
* Request `DMICRT` (writes FLDCRT for this criterion), `LE`, `PEEQ`, `STATUS` and `SDEG` field output.
* Use symmetry only if the strain path and the expected failure are symmetric.

## References

* `references/fld_notes.md`: concepts, model checklist, post-processing and the Abaqus calls.
* `examples/README.md`: dome stretch with an illustrative power-law sheet and FLC.
* Related skills: `abaqus-explicit-impact` (energy balance), `abaqus-odb-extract`.

## Background

Distilled from an OhmFrame study reproducing published forming-limit tests with FLD damage and element
deletion. Only the generic method is included: the template uses a Nakajima-style dome with illustrative
values, not the study's geometry, material or data. This skill has the thinnest source base of the set
(one study); treat it as a starting point.
