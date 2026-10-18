# Abaqus/Explicit checklist (impact, crash, drop, pull-out)

## Before submitting

- [ ] **Units consistent.** mm-t-s-N-MPa: steel density 7.85e-9, g = 9810, energies in mJ.
      A density off by 1e9 shows up as a stable increment off by about 3e4.
- [ ] **Stable increment estimate.** dt ≈ L_min / c, c = sqrt(E/rho) (steel ≈ 5.1e6 mm/s).
      A 2 mm element -> about 4e-7 s. Number of increments = T / dt: above ~1e6, rethink (time
      scaling, mesh) and use double precision above ~300k.
- [ ] **Smallest elements found** (Mesh > Verify > Stable Time Increment, or the .sta's first increment).
      One sliver can control the whole run.
- [ ] **Mass scaling decided on purpose.** Impact: none, or only below-minimum on a few small
      elements (`SEMI_AUTOMATIC, BELOW_MIN`). Quasi-static: allowed, check DMASS and ALLMW.
- [ ] **Hourglass control**: C3D8R/S4R with ENHANCED (or relax stiffness for large deformation); at least 3
      elements through the thickness for bending in solids.
- [ ] **Contact**: general contact (`All* with self`) unless you need pair-specific behaviour. Check the
      initial overclosures in the .msg; shell thickness offsets count. Rigid parts: discrete rigid with an RP that
      carries mass and inertia.
- [ ] **Initial conditions**: velocity on the RP (or the whole impactor), set in Initial; gap small (time to contact
      = gap / v) so you are not paying for free flight.
- [ ] **Outputs**: whole-model energies at ~200-500 points; contact forces (CFN) or RP reaction; field output
      sparse (20-50 frames). Restart every N intervals with overlay for long runs.
- [ ] **Element deletion** only with a damage law and `elemDeletion=ON`, `maxDegradation` ~0.99; request STATUS.

## After the run

Run `energy_balance.py`. Then:

| Check | Rule of thumb | If it fails |
|---|---|---|
| ALLAE / ALLIE | < 5 % (10 % max) | finer mesh, enhanced hourglass, C3D8I/fully integrated in hot spots |
| ETOTAL drift | ~constant, < 1-2 % of max energy | contact pops, mass scaling, single precision |
| ALLKE / ALLIE (quasi-static) | < 5-10 % after the start | longer step time or smooth-step amplitude |
| DMASS | < 2-5 % (and not in the impact zone) | lower the target dt, exclude the impact region |
| Initial ALLKE | = 0.5 m v^2 | wrong mass/units/velocity region |
| Contact force | impulse ∫F dt ≈ m Δv | missing contact pair, wrong surface side |

## Recipes

**Drop / ball impact** (`build_drop_test.py`): rigid impactor + point mass, clamped target, general contact,
no mass scaling, energy balance + impulse check.

**Headform / pedestrian-type impact on a panel**: same pattern; the impactor velocity and angle come from the
test protocol; output RP acceleration (A1-A3) at high rate and filter (CFC/SAE filters) in post-processing,
never inside Abaqus; criteria such as HIC are computed from the filtered acceleration.

**Vehicle or heavy mass hitting a structure**: lumped mass + deformable crush zone or a calibrated
force-displacement connector; check the global momentum (∫F dt), not only peak force; run long enough for
the rebound.

**Quasi-static pull-out / crush in Explicit** (when Standard will not converge, e.g. heavy contact or failure):
1. Displacement control on a rigid grip with a SMOOTH_STEP amplitude.
2. Step time ≥ ~10x the lowest natural period of the specimen (start there, then check ALLKE/ALLIE).
3. Mass scaling to a target dt (semi-automatic, whole model) is acceptable: check DMASS and ALLMW.
4. Report force from the grip RP reaction (or contact force) against grip displacement.
5. Contact force output (CFN) is written for both sides of a pair (A/B and B/A); de-duplicate before
   summing (see abaqus-odb-extract `--contact`).
6. Repeat with half the loading rate: if the curve changes, it was not quasi-static.
