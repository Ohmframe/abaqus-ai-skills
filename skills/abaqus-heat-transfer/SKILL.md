---
name: abaqus-heat-transfer
description: Build and post-process Abaqus heat-transfer models - steady-state and transient conduction through layered walls, slabs and construction details with film (convection) and radiation boundaries, and U-value or heat-flux extraction from the ODB. Use when the user needs a thermal analysis in Abaqus, a U-value or thermal-bridge check, temperature profiles through a build-up, or a transient (for example daily-cycle) thermal response.
---

# Abaqus heat transfer

> **Status: verified on Abaqus 2023.** The three-layer wall example gives U = 0.29788 W/m2K against
> the 0.29788 hand value (0.00 %) and interface temperatures matching the 1D hand calculation to
> 0.01 degC; the transient variant also runs. Not yet run on any other release. Still check your own
> model against the 1D hand calculation and tell the user so. See `TEST_REPORT.md`.

Conduction problems built by script, compared with the 1D hand calculation, then post-processed with
volume-weighted heat fluxes.

## When to use

* U-values, heat flux and interface temperatures through a layered build-up (wall, roof, floor, slab).
* Thermal bridges and 2D/3D details (linear thermal transmittance ψ against the 1D build-up).
* Transient response to a time-varying boundary (time lag, peak temperatures, daily cycles).
* Not for: coupled thermal-stress models (start from `abaqus-model-builder` with C3D8T elements and a
  coupled temperature-displacement step).

## Files

| Path | Run with | Purpose |
|---|---|---|
| `scripts/build_layered_slab.py` | `abaqus cae noGUI=build_layered_slab.py [-- spec.json] [submit]` | Layered block (one partitioned cell per layer), DC3D8 elements, films h = 1/Rsi and 1/Rse, steady or transient with a tabular outside temperature; writes the 1D hand calculation (`*_handcalc.json`) |
| `scripts/u_value.py` | `abaqus python u_value.py job.odb --set ALL_LAYERS --dT 20 [--dir 1] [--area A]` | EVOL-weighted mean HFL over an element set -> q and U |
| `../abaqus-model-builder/scripts/build_from_spec.py` | spec with `heat_steady`/`heat_transient` steps and `film` | General geometry (details, thermal bridges) |

## Workflow

1. **Collect** layers (t, k, ρ, c_p), boundary temperatures, surface resistances, and whether the
   question is steady (U-value, surface temperatures) or transient (time lag, peaks).
2. **Hand calculation first**: R = Rsi + Σ t/k + Rse, U = 1/R, q = U ΔT; the build script prints it.
3. **Build**: layered slab for 1D, model builder for 2D/3D details. Use SI (m, kg, s, W, °C) for
   building physics; temperatures in °C need `absoluteZero=-273.15` (the scripts set it).
4. **Run**; in transient runs check the `.msg` for cutbacks from the `deltmx` limit (maximum
   temperature change per increment).
5. **Extract** with `u_value.py` and compare (below). Report U, q and interface temperatures; for
   details also the extra heat loss compared with the 1D build-up.

## Checks before you report

* A 1D model of a 1D problem matches the hand calculation to well under 1 % (q, U and interface
  temperatures); only then trust a 2D/3D detail.
* Steady state: heat in = heat out (sum of RFL at prescribed-temperature nodes, or the film heat flows
  on both faces).
* Units: in mm-tonne-s, k keeps its SI number but h, ρ and c_p do not (see the notes). Prefer SI.

## Rules

* Pure conduction uses heat-transfer elements (DC3D8, DC3D4, DC2D4; temperature DOF 11 only).
* Films go on the outer faces only; internal faces between partitioned layers are not boundaries.
* Radiation needs `absoluteZero` and `stefanBoltzmann` set on the model.
* Imperfect contact between parts needs `ThermalConductance` in the contact property; a tie is perfect contact.
* Request NT, HFL, RFL and EVOL output; EVOL is needed for volume-weighted averages.

## References

* `references/heat_transfer_notes.md`: elements and steps, boundary-condition calls, outputs, unit pitfalls.
* `examples/README.md`: three-layer wall, U = 0.2979 W/m²K, q = 5.958 W/m² at ΔT = 20 K.
* Related skills: `abaqus-model-builder`, `abaqus-odb-extract`.

## Background

Distilled from OhmFrame work on steady and transient thermal performance of multi-layer build-ups
(layer materials, surface films, U-value post-processing). Generic only; the example uses textbook values.
