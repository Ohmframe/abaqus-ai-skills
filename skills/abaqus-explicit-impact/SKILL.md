---
name: abaqus-explicit-impact
description: Set up, run and sanity-check Abaqus/Explicit impact and dynamic-contact models - drop tests, impactor/headform hits on panels, vehicle or mass impacts on structures, and quasi-static pull-out or crush run in Explicit - with energy-balance (ALLKE/ALLIE/ALLAE/ETOTAL/DMASS) checks. Use when the user needs an explicit dynamic analysis, asks about mass scaling, stable time increment, hourglassing or energy balance, or wants to know whether an explicit result can be trusted.
---

# Abaqus/Explicit impact

OhmFrame workflow for explicit dynamic models: build from parameters, check the time step
before running, and never report a result without the energy balance.

## Scripts

| Script | Run with | Purpose |
|---|---|---|
| `scripts/build_drop_test.py` | `abaqus cae noGUI=build_drop_test.py [-- submit]` | Parameterised template: rigid impactor (RP + mass/inertia, initial velocity) on a clamped plate, general contact with friction, optional damage/element deletion, optional mass scaling, energy and RP histories |
| `scripts/energy_balance.py` | `abaqus python energy_balance.py job.odb --mode impact\|quasistatic [--ke0 X]` | Energy CSV and PASS/WARN/FAIL checks: hourglass, ETOTAL drift, KE/IE (quasi-static), DMASS, ALLMW, viscous damping, initial KE |
| `../abaqus-odb-extract/scripts/odb_extract.py` | `abaqus python ... --history-set RP --energies --contact` | RP histories, energies, de-duplicated contact forces |

For anything that is not plate + impactor, build with `abaqus-model-builder`
(`build_from_spec.py` supports explicit steps, mass scaling, restart, general contact, predefined velocity).

## Workflow

1. **Classify**: true impact (inertia matters, no mass scaling in the impact zone) or quasi-static
   in Explicit (pull-out, crush, forming: mass/time scaling allowed, KE/IE must stay small).
2. **Units and dt first**: write the unit system down; estimate dt = L_min / sqrt(E/rho) and the
   increment count before building. See `references/explicit_checklist.md`.
3. **Build** from parameters (template or spec). Impactors: rigid + RP with mass and inertia, velocity
   as a predefined field. Contact: general contact unless there is a reason not to.
4. **Data check**: `abaqus job=NAME datacheck interactive`; read the .msg for initial overclosures and the
   .sta/.msg for the stable increment and the controlling elements (`check_logs.py` in abaqus-model-builder).
5. **Run**, watch the .sta (increment count, dt, % mass change, energy).
6. **Prove**: `energy_balance.py` (must not FAIL), initial KE equals the hand value, impulse ≈ m Δv,
   then the engineering results (peak force, deflection, acceleration, plastic strain).
7. **Report** the checks table with the results. State what is mass-scaled and by how much.

## Rules

* Mass scaling in an impact zone changes the physics. Say so if it is used.
* Filter accelerations (CFC/SAE) after extraction, not with Abaqus output filters, and say which filter.
* Contact forces from CFN come twice per pair (A/B and B/A); de-duplicate.
* Double precision (`explicitPrecision=DOUBLE_PLUS_PACK`) for runs beyond ~300k increments.
* Long runs: `step.Restart(numberIntervals=N, overlay=ON)` so a crash does not lose everything.

## Lessons behind this skill

Built from OhmFrame production work on a vehicle front-end impact study (impactor on a
panel with energy checks), a heavy-vehicle impact on a structure, and a quasi-static
pull-out of an embedded element run in Explicit. Only the generic setup and checks are
included; the worked example is a textbook drop test.
Scripts untested on Abaqus by OhmFrame (see the example README for the hand checks to compare against).
