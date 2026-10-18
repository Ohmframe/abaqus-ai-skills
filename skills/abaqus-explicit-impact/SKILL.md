---
name: abaqus-explicit-impact
description: Set up, run and sanity-check Abaqus/Explicit impact and dynamic-contact models - drop tests, impactor or headform hits on panels, vehicle or heavy-mass impacts on structures, and quasi-static pull-out or crush run in Explicit - with energy-balance checks (ALLKE, ALLIE, ALLAE, ETOTAL, DMASS, ALLMW). Use when the user needs an explicit dynamic analysis, asks about mass scaling, the stable time increment, hourglassing or the energy balance, or wants to know whether an explicit result can be trusted.
---

# Abaqus/Explicit impact

> **Status: verified on Abaqus 2023.** The drop-test example gives initial ALLKE 12 500.01 mJ vs the
> 12 500 mJ hand value (0.0001 %), stable increment 6.1e-7 s and 4 833 increments inside the predicted
> ranges, energy drift 0.022 %, `energy_balance.py` OVERALL PASS. On your own model, report results only
> after the energy balance and hand checks below pass. Abaqus 2024+ is not yet tested. See `TEST_REPORT.md`.

Explicit dynamic models built from parameters: check the time step before running, and never report
a result without the energy balance.

## When to use

* Drop tests, impactor or headform hits on panels, vehicle or heavy-mass impacts on structures.
* Quasi-static pull-out, crush or forming run in Explicit because Standard will not converge.
* Questions on mass scaling, stable time increment, hourglass energy, element deletion, energy balance.
* Not for: implicit (Standard) statics or dynamics (`abaqus-model-builder`), sheet-forming limits
  (`abaqus-forming-fld`, which uses this skill's energy check).

## Files

| Path | Run with | Purpose |
|---|---|---|
| `scripts/build_drop_test.py` | `abaqus cae noGUI=build_drop_test.py [-- submit]` | Parameterised template: rigid impactor (RP with mass and inertia, initial velocity) on a clamped S4R or C3D8R plate, general contact with friction, optional ductile damage and element deletion, optional mass scaling, energy and RP histories |
| `scripts/energy_balance.py` | `abaqus python energy_balance.py job.odb --mode impact\|quasistatic [--ke0 X] [--step S]` | Energy CSV and PASS/WARN/FAIL checks: hourglass, ETOTAL drift, KE/IE (quasi-static), DMASS, ALLMW, viscous dissipation, initial KE |
| `../abaqus-odb-extract/scripts/odb_extract.py` | `abaqus python odb_extract.py job.odb --history-set RP --energies --contact` | RP histories, energies, de-duplicated contact forces |

Anything other than plate + impactor: build with `abaqus-model-builder` (`build_from_spec.py` supports
explicit steps, mass scaling, restart, general contact and predefined velocity).

## Workflow

1. **Classify**: true impact (inertia matters; no mass scaling in the impact zone) or quasi-static in
   Explicit (pull-out, crush, forming: mass or time scaling allowed, ALLKE/ALLIE must stay small).
2. **Units and dt first**: write the unit system down (for example mm-tonne-s-N-MPa, energy in mJ, steel
   density 7.85e-9 t/mm³). Estimate dt ≈ L_min / c with c = sqrt(E/ρ) (steel ≈ 5.2e6 mm/s) and the
   increment count T / dt before building. See `references/explicit_checklist.md`.
3. **Build** from parameters (template or spec). Impactors: rigid body with an RP carrying mass and
   rotary inertia, velocity as a predefined field in the Initial step. Contact: general contact
   (all with self) unless there is a reason not to.
4. **Datacheck**: `abaqus job=NAME datacheck interactive`; read the `.msg` for initial overclosures and
   the stable increment with the controlling elements (`check_logs.py` in `abaqus-model-builder`).
5. **Run** and watch the `.sta`: increment count, dt, % mass change, total energy.
6. **Prove** (below), then extract the engineering results (peak force, deflection, acceleration,
   plastic strain).
7. **Report** the checks table with the results; state what is mass-scaled and by how much, which
   filter was applied to accelerations, and which Abaqus release you ran (these scripts are verified
   on 2023 only).

## Checks before you report

* `energy_balance.py` does not FAIL: ALLAE/ALLIE below about 5 % (10 % max), ETOTAL roughly constant
  (drift below 1-2 % of the peak energy), DMASS small and not in the impact zone.
* Initial ALLKE equals ½ m v² from the hand calculation (wrong mass, units or velocity region otherwise).
* Impulse: ∫F dt ≈ m Δv from the contact force or RP history.
* Quasi-static runs: ALLKE/ALLIE below 5-10 % after the start, and the curve does not change when the
  loading rate is halved.

## Rules

* Mass scaling in an impact zone changes the physics. Say so if it is used.
* Filter accelerations (CFC/SAE classes) after extraction, not with Abaqus output filters, and say which filter.
* Contact forces from CFN history come twice per pair (A/B and B/A): de-duplicate before summing.
* Double precision for runs beyond about 300 000 increments: `explicitPrecision=DOUBLE_PLUS_PACK` on the
  job, or `double=both` on the command line.
* Long runs: `step.Restart(numberIntervals=N, overlay=ON)` so a crash does not lose everything; continue
  with `abaqus job=NAME recover`.
* Reduced-integration elements (C3D8R, S4R) need hourglass control (`hourglassControl=ENHANCED`) and at
  least 3 elements through the thickness for solids in bending.
* Element deletion only with a damage law and `elemDeletion=ON`; request `STATUS` output.

## References

* `references/explicit_checklist.md`: before-submit checklist, after-run table, recipes (drop, headform,
  heavy-mass impact, quasi-static pull-out).
* `examples/README.md`: 1 kg sphere at 5 m/s on a clamped 2 mm steel plate (KE0 = 12 500 mJ).
* Related skills: `abaqus-model-builder`, `abaqus-odb-extract`, `abaqus-forming-fld`.

## Background

Distilled from OhmFrame production work on impactor-on-panel studies with energy checks, heavy-mass
impacts on structures, and quasi-static pull-out of embedded parts run in Explicit. Only the generic
setup and checks are included; the worked example is a textbook drop test.
