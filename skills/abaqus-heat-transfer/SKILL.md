---
name: abaqus-heat-transfer
description: Build and post-process Abaqus heat-transfer models - steady-state and transient conduction through layered walls, slabs and details with film (convection) and radiation boundaries, and U-value / heat-flux extraction from the ODB. Use when the user needs a thermal analysis in Abaqus, a U-value or thermal-bridge check, temperature profiles through a build-up, or a transient (daily cycle) thermal response.
---

# Abaqus heat transfer

OhmFrame workflow for conduction problems: build by script, compare with the 1D hand calculation,
then extract area-weighted fluxes.

## Scripts

| Script | Run with | Purpose |
|---|---|---|
| `scripts/build_layered_slab.py` | `abaqus cae noGUI=build_layered_slab.py [-- spec.json] [submit]` | Layered block (one partitioned cell per layer), DC3D8, films h = 1/Rsi and 1/Rse, steady or transient with a tabular outside temperature; writes the 1D hand calc (`*_handcalc.json`) |
| `scripts/u_value.py` | `abaqus python u_value.py job.odb --set ALL_LAYERS --dT 20` | EVOL-weighted mean HFL over an element set -> q and U |
| `../abaqus-model-builder/scripts/build_from_spec.py` | spec with `heat_steady`/`heat_transient` steps and `film` | general geometry (details, thermal bridges) |

## Workflow

1. Collect layers (t, k, rho, cp), boundary temperatures, surface resistances and whether the
   question is steady (U-value, condensation-risk temperatures) or transient (time lag, peak).
2. Do the 1D hand calc first (`R = Rsi + Σ t/k + Rse`); the script prints it.
3. Build: layered slab for 1D, or the model builder for 2D/3D details. Use SI metres.
4. Run; check the .msg for "temperature change exceeds DELTMX" cutbacks in transient runs.
5. Extract with `u_value.py`; compare a 1D model with the hand calc (should agree within 1 %) before trusting
   the 2D/3D detail. Report U, q, interface temperatures, and for details the extra loss vs 1D.

Notes: `references/heat_transfer_notes.md`. Example: `examples/README.md`.

## Lessons behind this skill
From OhmFrame work on steady and transient thermal performance of a multi-layer wall
build-up (layer materials, surface films, U-value post-processing). Generic only; the example uses
textbook values. Scripts untested on Abaqus by OhmFrame.
