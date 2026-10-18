# Mesh quality criteria

Two different checks exist in Abaqus and they disagree. Report both.

## 1. Analysis Checks (what the solver will warn about)

`p.verifyMeshQuality(criterion=ANALYSIS_CHECKS)` returns `failedElements` (errors: the job will
stop) and `warningElements` (job runs, the .dat lists them). These are the checks the
pre-processor applies when writing the input:

| Element | Error | Warning (typical) |
|---|---|---|
| hex / quad, isoparametric angle | < ~0 deg or negative Jacobian | outside 45-135 deg (the angle between lines joining opposite face centres) |
| tet / tri, face corner angle | degenerate | < 5-10 deg or > 160-170 deg |
| any | zero/negative volume | aspect ratio far above 10 (very element dependent) |

Exact limits depend on the element type and release; take the counts from the tool, not from this table.

## 2. Verify Mesh shape metrics (the GUI dialog)

| Criterion | Dialog default | Meaning |
|---|---|---|
| `SHAPE_FACTOR` | < 0.0001 (tets) | normalised tet quality |
| `SMALL_ANGLE` | 10 deg | smallest face corner angle |
| `LARGE_ANGLE` | 160 deg | largest face corner angle |
| `ASPECT_RATIO` | 10 | longest / shortest edge |
| `GEOM_DEVIATION_FACTOR` | 0.2 | chordal deviation from the geometry |
| `MIN_SIZE` / `MAX_SIZE` | user | element edge length |
| `STABLE_TIME_INCREMENT` (explicit) | user | estimated element dt; find the elements controlling the time step |

Call: `p.verifyMeshQuality(criterion=SMALL_ANGLE, threshold=10.0)`.

## What actually matters

* **Errors**: must be zero.
* **Warnings in the result region**: fix them. Warnings far from the region of interest, in
  regions with low gradients, are usually acceptable; say so in the report.
* **Shells**: free element edges inside the structure (not on the real boundary) mean
  unconnected panels. Edges shared by 3+ elements are T-junctions: fine where intended,
  a defect where two skins were meant to be one.
* **Explicit**: the smallest elements control the stable increment. One sliver can make
  the run 10x slower; use STABLE_TIME_INCREMENT to find it.
* Element formulation beats perfect shape: linear C3D8R in bending with 1 element through the
  thickness is worse than slightly skewed C3D8I with 4.
