# Worked example: sphere dropped on a clamped plate

`../scripts/build_drop_test.py` with its default parameters: a 1 kg rigid sphere (R 25 mm) at
5 m/s onto a 200 x 200 x 2 mm clamped steel plate (S4R, bilinear plasticity). Units mm-t-s-N-MPa.

```bash
abaqus cae noGUI=../scripts/build_drop_test.py -- submit
abaqus python ../scripts/energy_balance.py drop_test.odb --mode impact --ke0 12500
abaqus python ../../abaqus-odb-extract/scripts/odb_extract.py drop_test.odb \
       --history-set RP_IMPACTOR --history-var U3 --history-var V3 --energies --out results
```

## Hand checks

| Quantity | Value | How |
|---|---|---|
| initial kinetic energy | **12 500 mJ** (12.5 J) | 0.5 x 1e-3 t x (5000 mm/s)^2 |
| time to contact | 1.0e-4 s | gap 0.5 mm / 5000 mm/s |
| stable increment (plate) | ≈ 4-7e-7 s | 4 mm / 5.4e6 mm/s (plate wave speed sqrt(E / (ρ (1 - ν²)))) ≈ 7.4e-7 s; the element-by-element estimate Abaqus uses is lower, so expect 4-7e-7 s |
| increments for 3 ms | ≈ 4 000-8 000 | 3e-3 s / dt; single precision is fine |
| static stiffness bound | the plate cannot stop the sphere elastically: the 12.5 J ends mostly as ALLPD (plastic work) plus rebound ALLKE | energy balance |
| impulse | ∫F dt = m (v_in + v_out) | from the RP V3 history |

## What you should see

* `energy_balance.py`: ke0 PASS (≈ 0 %), drift PASS, hourglass PASS or WARN (coarse S4R),
  overall PASS/WARN.
* ALLKE falls from 12 500 mJ; ALLIE (mostly ALLPD) rises; ETOTAL stays ~flat.
* RP V3 goes from -5000 mm/s through zero to a small positive rebound value.

## Result on Abaqus 2023 (verified)

| Quantity | Hand estimate | Abaqus 2023 | Error |
|---|---|---|---|
| initial kinetic energy | 12 500 mJ | **12 500.01 mJ** | 0.0001 % |
| stable increment | 4-7e-7 s | **6.12e-7 s** | in range |
| increments for 3 ms | 4 000-8 000 | **4 833** | in range |
| energy at the end | ETOTAL about flat | ALLPD 8 012, ALLSE 965, ALLKE 3 292, ALLAE 190, ETOTAL 12 500 mJ | drift 0.022 % |
| RP V3 | -5 000 mm/s to a small positive rebound | **-5 000 -> +2 424 mm/s** | - |
| `energy_balance.py` | PASS or WARN | **OVERALL PASS**: hourglass 2.09 %, drift 0.022 %, ke0 0.000 %, dmass 0 % | - |

2 500 S4R plus 941 R3D4; build 2 s, solve 23 s on 2 CPUs. The 18 `.dat` warnings are all benign
("output request S/PEEQ/STATUS is not available for element type R3D4/MASS/ROTARYI", i.e. the
field request also covers the rigid impactor).
