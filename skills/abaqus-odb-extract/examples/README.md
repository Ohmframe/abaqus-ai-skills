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

> Not yet run in Abaqus. These are the hand-calculation targets.
