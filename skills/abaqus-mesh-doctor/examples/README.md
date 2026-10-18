# Worked example: plate with a hole, structured hex

`plate_hole_hex.py` builds a quarter model of a 200 x 200 x 5 mm steel plate with a
40 mm central hole under 100 MPa remote tension (mm, N, MPa). It shows the core move
in this skill: **partition the geometry until every cell is a 4-sided sweepable block**, then
mesh STRUCTURED hex and confirm it with Analysis Checks.

```bash
abaqus cae noGUI=plate_hole_hex.py              # build, mesh, verify, write plate_hole.inp/.cae
abaqus cae noGUI=plate_hole_hex.py -- submit    # also solve
abaqus cae noGUI=../scripts/mesh_diagnose.py -- plate_hole.cae model:PLATE_HOLE part:PLATE
```

## What you should see

| Check | Expected |
|---|---|
| cells after the butterfly cut | 2 |
| non-hex elements | 0 |
| Analysis Checks errors / warnings | 0 / 0 |
| mesh colour in the GUI (Mesh module) | green (structured) for both cells |

Remove the `PartitionCellByPlaneThreePoints` line and re-run: the single 5-sided cell can no
longer be meshed STRUCTURED. That is the failure this skill is about.

## Hand calculation for the solved job

* Infinite plate (Kirsch): sigma_max = 3 x sigma = **300 MPa** at the hole edge on the y axis.
* Finite width (Heywood, as given in Peterson's tables): d/W = 0.2, Kt_net = 2 + (1 - 0.2)^3 = 2.512,
  net-section stress = 100 x 200 / 160 = 125 MPa, so sigma_max ≈ **314 MPa**.
* Expect S11 at node set `HOLE_TOP` in the 300-320 MPa range. With the default seeds
  (12 elements per 45° of arc, linear C3D8I) it should land within a few percent.
* Reaction check: the sum of RF1 on set `X0` = -sigma x (H/2) x t = **-50 000 N** (100 MPa x 100 mm x 5 mm).

## Result on Abaqus 2023 (verified)

| Check | Expected | Abaqus 2023 |
|---|---|---|
| cells after the butterfly cut | 2 | **2** |
| non-hex elements | 0 | **0** |
| Analysis Checks errors / warnings | 0 / 0 | **0 / 0** |
| mesh | - | 624 C3D8I, 1 050 nodes |
| S11 max (integration points) | 300-320 MPa | **319.86 MPa**, i.e. Kt = 3.20, 1.9 % above the 314 MPa Heywood value |
| S11 at node set HOLE_TOP | - | **331-341 MPa**, extrapolated to the nodes so above the integration-point peak |
| RF1 sum on set X0 | -50 000 N | **-50 000 N** |

Build 2 s, solve 15 s. `mesh_diagnose.py` on the result reports cell controls
`{'HEX/STRUCTURED': 2}`, 0 free geometry edges and 0 bad elements. If your numbers differ, check
the seed directions on the biased radial edges first.
