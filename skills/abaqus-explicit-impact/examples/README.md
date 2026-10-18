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
| stable increment (plate) | ≈ 7e-7 s | 4 mm / 5.1e6 mm/s ... less with the shell thickness and Poisson, so expect 4-7e-7 |
| increments for 3 ms | ≈ 5 000-8 000 | single precision is fine |
| static stiffness bound | the plate cannot stop the sphere elastically: the 12.5 J ends mostly as ALLPD (plastic work) plus rebound ALLKE | energy balance |
| impulse | ∫F dt = m (v_in + v_out) | from the RP V3 history |

## What you should see

* `energy_balance.py`: ke0 PASS (≈ 0 %), drift PASS, hourglass PASS or WARN (coarse S4R),
  overall PASS/WARN.
* ALLKE falls from 12 500 mJ; ALLIE (mostly ALLPD) rises; ETOTAL stays ~flat.
* RP V3 goes from -5000 mm/s through zero to a small positive rebound value.

Status: **not yet run in Abaqus**. The numbers above are hand estimates to sanity-check the run, not results.
