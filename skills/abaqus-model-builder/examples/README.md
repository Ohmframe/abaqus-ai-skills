# Worked example: steel cantilever with a tip load

A textbook case with a closed-form answer, so you can confirm the whole chain works
(spec -> `.cae` -> job -> logs -> ODB) before you build anything real.

| Item | Value |
|---|---|
| Length L | 1000 mm (global X) |
| Section | 100 mm deep (Y) x 50 mm wide (Z) |
| Material | E = 210 000 MPa, nu = 0.3 |
| Support | Encastre at x = 0 |
| Load | P = 1000 N in -Y at the tip, applied to an RP with a kinematic coupling to the tip face |
| Mesh | 10 mm C3D8I (incompatible modes, good in bending): 100 x 10 x 5 elements |

## Hand calculation

- I = b h^3 / 12 = 50 x 100^3 / 12 = 4.167e6 mm^4
- Bending tip deflection: delta_b = P L^3 / (3 E I) = 1000 x 1000^3 / (3 x 210000 x 4.167e6) = **0.381 mm**
- Shear correction (Timoshenko, kappa = 5/6, G = 80 770 MPa): delta_s = P L / (kappa G A) = **0.003 mm**
- Total: **about 0.384 mm**
- Bending stress at mid-span (x = 500 mm): sigma = M c / I = 1000 x 500 x 50 / 4.167e6 = **6.0 MPa**
  (read S11 at mid-span, away from the clamped end where the encastre causes local Poisson stresses)
- Reaction at the support: RF2 sum = **+1000 N**

## Run it

```bash
python ../scripts/validate_spec.py cantilever_beam.json
../scripts/run_job.sh cantilever_beam.json Cantilever --datacheck
abaqus python ../../abaqus-odb-extract/scripts/odb_extract.py Cantilever.odb \
    --field U:U2 --field S:S11 --reactions FIXED_END --history-set RP_TIP --out post
```

Expect U2 at RP_TIP of about -0.38 mm (within 2 % of the hand value), a support reaction sum of
1000 N, and zero errors in the log check. A larger difference points to the mesh (try C3D8R: it
needs at least 4 elements through the depth) or to the coupling.

> We have not run this example in Abaqus yet. The numbers above are the hand-calculation targets.
> Please report what you get.
