# Worked example: hemispherical punch stretch, illustrative material

`../scripts/build_dome_stretch.py` with its defaults: quarter of a 200 mm diameter, 1 mm blank,
flange locked beyond r = 80 mm, 100 mm diameter rigid punch, 40 mm stroke, generic power-law
sheet (K = 500 MPa, n = 0.22) and a textbook-shaped FLC with FLC0 = 0.30. Units mm-t-s-N-MPa.
**The material and FLC are illustrative only.**

```bash
abaqus cae noGUI=../scripts/build_dome_stretch.py -- submit
abaqus python ../scripts/fld_extract.py dome.odb --rp-set RP_PUNCH
abaqus python ../../abaqus-explicit-impact/scripts/energy_balance.py dome.odb --mode quasistatic
```
Strain-path series: set `STRIP_WIDTH` to 20, 50, 80, 120 and re-run; the onset points should walk from the
left (uniaxial) side of the FLD toward the right (biaxial) side.

## Sanity checks (not results)

| Check | Expectation |
|---|---|
| initial yield printed by the build script | K x 0.005^0.22 ≈ 156 MPa |
| strain path at the pole, full disc | near equi-biaxial: minor ≈ major |
| onset | FLDCRT reaches 1 before the full 40 mm stroke for the default FLC (if not, increase DEPTH) |
| failure location | near the pole with low friction, moving out toward the punch radius as friction increases |
| quasi-static | ALLKE/ALLIE PASS or WARN; if FAIL, increase T_END or reduce mass scaling |
| Considère (uniaxial) | necking strain ≈ n = 0.22: the left-side FLC should not sit far below it |

## Result on Abaqus 2023 (verified mechanics, illustrative material)

| Check | Expectation | Abaqus 2023 |
|---|---|---|
| initial yield printed by the build script | about 156 MPa | **155.9 MPa** |
| strain path at the pole, full disc | minor about equal to major | **major 0.441, minor 0.403**, near equi-biaxial |
| onset | FLDCRT reaches 1 before the full stroke | **onset at 53.7 mm of the 70 mm stroke** (frame 26) |
| failure | element deletion, punch force collapse | **15.6 kN -> 3.5 kN within two output frames** |
| quasi-static | ALLKE/ALLIE PASS or WARN | **PASS, 0.15 %**; `energy_balance.py` OVERALL PASS |
| Considere, uniaxial | FLC left side not far below n = 0.22 | FLC0 = 0.30 > 0.22 |
| strain-path series, `STRIP_WIDTH = 50` | onset walks toward the uniaxial side | **minor 0.403 -> -0.046, major 0.441 -> 0.598** |

Build 3 s, solve 3 min on 4 CPUs (2 395 S4R plus 6 613 R3D4, about 100 k increments).

Two defaults changed after this run: `DEPTH` 40 -> 70 mm (at 40 mm the criterion only reaches 0.65,
so there is no onset at all) and `MASS_SCALING_DT` 5e-7 -> `None` (5e-7 added about 280 % mass on
the 2 mm seed, which `energy_balance.py` rightly FAILs, and it softened the peak punch force by
about 10 %). The material and FLC remain **illustrative**.
