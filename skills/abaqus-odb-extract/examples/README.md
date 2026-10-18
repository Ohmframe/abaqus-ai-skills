# Worked example: post-process the cantilever

This uses `Cantilever.odb` from the `abaqus-model-builder` example (a steel cantilever, P = 1000 N,
L = 1000 mm, section 100 x 50 mm).

```bash
abaqus python ../scripts/odb_probe.py Cantilever.odb
abaqus python ../scripts/odb_extract.py Cantilever.odb \
    --field U:U2 --field U:MAGNITUDE --field S:MISES --field S:S11 \
    --reactions FIXED_END --history-set RP_TIP --out post
```

## Checks to make in `post/summary.json`

| Quantity | Where | Expected (hand calculation) |
|---|---|---|
| Tip deflection | `history` -> `RP_TIP` -> `U2.last` | about -0.384 mm |
| min U2 | `fields` -> U:U2 `min` | about -0.384 mm (the tip) |
| Support reaction | `reactions` -> FIXED_END `last.RF2` | +1000 N (equilibrium, to 4+ digits) |
| S11 at mid-span | `field_S_S11_*.csv`, elements near x = 500 | about +/-6 MPa |
| Peak Mises | `fields` -> S:MISES `max` | about 12 MPa nominal at the root, higher locally from the clamp |

If the support reaction doesn't balance the applied load, stop. Something in the set-up is
wrong (load region, BC region or units). Don't go on to stresses until it balances.

## Result on Abaqus 2023 (verified)

| Quantity | Expected | Abaqus 2023 |
|---|---|---|
| `history` -> RP_TIP -> `U2.last` | about -0.384 mm | **-0.381909 mm** |
| `fields` -> U:U2 `min` | about -0.384 mm at the tip | **-0.38191 mm** at `ASSEMBLY.1` (the RP) |
| `reactions` -> FIXED_END `last.RF2` | +1000 N | **+999.99997 N** |
| `fields` -> S:MISES `max` | about 12 MPa nominal at the root | **12.638 MPa** |
| `fields` -> S:S11 | about +/-6 MPa at mid-span | **+/-13.446 MPa** peak at the root, 5.40 MPa at mid-span |

`--frame all`, `--energies` and `--contact` were also exercised on the Explicit drop-test ODB;
`--contact` reports a clear "no CFN/CFS history" message when none was requested.
