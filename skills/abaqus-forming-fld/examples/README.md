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

Status: **not yet run in Abaqus**.
