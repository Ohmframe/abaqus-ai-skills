# Worked example: U-value of a three-layer wall (steady state)

Default parameters of `../scripts/build_layered_slab.py`: a textbook build-up (values are generic
handbook-type figures, not from any project), inside at 20 °C, outside at 0 °C.

| Layer (inside -> outside... as modelled from x = 0) | t (m) | k (W/mK) | R = t/k |
|---|---|---|---|
| inside surface Rsi | - | - | 0.130 |
| BRICK | 0.100 | 0.77 | 0.1299 |
| INSULATION | 0.100 | 0.035 | 2.8571 |
| BLOCK | 0.100 | 0.50 | 0.2000 |
| outside surface Rse | - | - | 0.040 |
| **total** | | | **3.3570 m²K/W** |

U = 1/R = **0.2979 W/m²K**, q = U x 20 K = **5.958 W/m²**.

Interface temperatures (from x = 0): surface 19.23 °C, BRICK|INSULATION 18.45 °C,
INSULATION|BLOCK 1.43 °C, outside surface 0.24 °C.

```bash
abaqus cae noGUI=../scripts/build_layered_slab.py -- submit      # writes slab_handcalc.json too
abaqus python ../scripts/u_value.py slab.odb --set ALL_LAYERS --dT 20
```

## What you should see

* `u_value.py`: q_mean ≈ 5.958 (sign depends on the flux direction: heat flows in +X), U ≈ 0.298.
  A 1D linear-element model of a 1D problem should match to well under 1 %.
* NT at the interfaces matches the table above.
* Transient variant: add the `"transient"` block (see the script header); the steady-state values are
  the long-time limit for constant temperatures.

Status: **not yet run in Abaqus**.
