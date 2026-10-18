# Test report: abaqus-ai-skills on Abaqus 2023

Every worked example in this repository was run end to end and compared with the hand calculation in
its own `examples/README.md`. This file records what was run, what came out, what was wrong and what
was changed.

| Item | Value |
|---|---|
| Abaqus release | **Abaqus 2023** (`abq2023`), Standard, Explicit and CAE |
| Platform | Windows 11, x86-64, local FlexNet licence server |
| Abaqus Python kernel | 2.7 (as shipped with 2023) |
| Host Python for the licence-free helpers | 3.12 |
| Branch | `test/abaqus-2023` |
| Scratch folder | `runs/<skill>/` (git-ignored; no `.cae`/`.inp`/`.odb` is committed) |
| Total solver wall-clock | about 6 minutes across all examples |

Commands used throughout: `abaqus cae noGUI=<script>` for model building, `abaqus job=<job>
input=<job>.inp cpus=N interactive ask_delete=OFF` for solving, `abaqus python <script>` for ODB
post-processing (no CAE token).

## Summary

| Skill | Verdict | Headline result vs hand calculation |
|---|---|---|
| `abaqus-model-builder` | **PASS** | tip deflection -0.38191 mm vs -0.384 mm (**0.5 %**); RF2 +1000.00 N vs +1000 N (**0.00 %**) |
| `abaqus-odb-extract` | **PASS** (1 bug fixed) | reproduces all of the above; field/reaction/history/energy paths all exercised |
| `abaqus-mesh-doctor` | **PASS** (1 bug fixed) | Kt 3.20 vs the 3.0-3.14 hand range (**1.9 %** vs Heywood 314 MPa); RF1 -50 000 N (**0.00 %**) |
| `abaqus-version-compat` | **PARTIAL** | same-release round trip is bit-identical; the cross-release step could not be tested (only 2023 installed) |
| `abaqus-explicit-impact` | **PASS** (1 bug fixed) | ALLKE0 12 500.01 mJ vs 12 500 mJ (**0.0001 %**); energy balance OVERALL PASS |
| `abaqus-heat-transfer` | **PASS** (1 bug fixed) | U 0.297884 W/m2K vs 0.29788 (**0.00 %**); all four interface temperatures within 0.01 degC |
| `abaqus-forming-fld` | **PASS** (mechanics) | onset at 53.7 mm, quasi-static PASS; the material and FLC are illustrative, so the *limit* is not verified |

Seven bugs were found and fixed. Every `.py` file in `skills/` still byte-compiles under both the
Abaqus 2023 Python 2.7 kernel and Python 3.12, and `py23_check.py` reports 0 errors / 0 warnings
across all 20 files.

---

## 1. `abaqus-model-builder` - PASS

Example: steel cantilever, L = 1000 mm, 100 x 50 mm section, P = 1000 N at the tip through an RP with
a kinematic coupling, 5 000 C3D8I elements.

```
python validate_spec.py cantilever_beam.json                   -> 0 errors, 0 warnings
abaqus cae noGUI=build_from_spec.py -- cantilever_beam.json     -> 6 s
abaqus job=Cantilever input=Cantilever.inp cpus=1 interactive   -> 17 s, COMPLETED
python check_logs.py Cantilever                                 -> completed True, 0 errors
run_job.sh cantilever_beam.json Cantilever --datacheck           -> build + datacheck + run + triage
```

| Quantity | Hand calculation | Abaqus 2023 | Error |
|---|---|---|---|
| Tip deflection U2 at RP_TIP | -0.384 mm | -0.381909 mm | **0.5 %** |
| Support reaction sum RF2 | +1000 N | +999.99997 N | **0.00 %** |
| S11, top fibre at mid-span | 6.0 MPa at the surface | 5.400 MPa at the integration points | see below |
| Analysis Checks errors / warnings | 0 / 0 | 0 / 0 | - |

The mesh reported 0 Analysis Checks errors and warnings, and all four selections (FIXED_END,
TIP_FACE, TOP_FIBRE_ROOT, RP_TIP) picked up the expected number of entities.

The S11 figure needed a closer look before it could be called a match. The integration points of the
top element layer sit at c = 42.1 and 47.9 mm and x = 495 and 505 mm; beam theory there gives
exactly 5.40 MPa, and the mean of all 80 integration points is 5.4000 MPa. The 6.0 MPa in the
example is the **surface** value, which you only see after nodal extrapolation. The example README
now says so.

### Fix 1 - `check_logs.py` reported a clean datacheck as a failure

A `datacheck` run on Abaqus 2023 writes no `.log` and no `.sta` at all; the only completion marker is
`ANALYSIS DATACHECK COMPLETE` in the `.dat`. `check_logs.py` therefore printed `completed: None` and
exited 1 for a perfectly clean datacheck, which made step 5 of the documented workflow look broken.
It now recognises that marker and sets `datacheck: true`.

`run_job.sh` works as documented (it uses `|| true` around the datacheck, so the old bug never
blocked a run). One usage note worth knowing: if you pass `SCRATCH=`, the directory must already
exist, or Abaqus aborts before writing anything.

## 2. `abaqus-odb-extract` - PASS

Run against the Standard cantilever ODB, the plate-with-hole ODB, the Explicit drop-test ODB and the
heat-transfer ODB. `odb_probe.py` listed steps, fields, history regions, instances and sets
correctly. `odb_extract.py` reproduced every number in section 1, summed reactions over a node set
every frame, dumped the RP history (U2/RF2/CF2), extracted whole-model energies with the KE/IE and
drift ratios, handled `--frame all` (31 frames) and reported a clear message rather than crashing
when `--contact` was asked for on a model with no CFN/CFS history requested.

### Fix 2 - `--region` on a node set crashed with "Invalid component label"

Restricting an integration-point field (S, E, PEEQ) to a **node** set returns an empty field from
`getSubset()`. The subsequent `getScalarField(componentLabel='S11')` then failed with
`OdbError: Invalid component label`, which says nothing about the real cause. This is exactly the
command the `abaqus-mesh-doctor` example documents (`--field S:S11 --region HOLE_TOP`), so the
documented workflow was broken.

`subset_region()` now retries at `ELEMENT_NODAL` (the values extrapolated to the nodes, which is what
you want when you ask for stress "at" a node set), prints a note saying so, and if that is also
empty raises a message that explains the element-set vs node-set mismatch.

## 3. `abaqus-mesh-doctor` - PASS

Example: quarter plate 200 x 200 x 5 mm, 40 mm central hole, 100 MPa remote tension, butterfly
partition, structured C3D8I.

| Check | Expected | Abaqus 2023 |
|---|---|---|
| cells after the butterfly cut | 2 | 2 |
| non-hex elements | 0 | 0 |
| Analysis Checks errors / warnings | 0 / 0 | 0 / 0 |
| mesh | - | 624 C3D8I, 1 050 nodes |
| S11 max (integration points) | 300-320 MPa | 319.86 MPa, i.e. **Kt = 3.20** |
| S11 at node set HOLE_TOP | - | 331-341 MPa (nodal extrapolation) |
| RF1 sum on set X0 | -50 000 N | -50 000 N (**0.00 %**) |

Against the finite-width Heywood value of 314 MPa the integration-point peak is **1.9 %** high;
against the infinite-plate Kirsch value of 300 MPa it is 6.6 % high, as expected for a 200 mm-wide
plate. Build 2 s, solve 15 s.

The other three scripts in the skill were run too:

* `mesh_diagnose.py` on `plate_hole.cae`: cell controls `{'HEX/STRUCTURED': 2}`, 0 free geometry
  edges, 0 bad elements, 0 failed shape metrics. Wrote `mesh_report.txt/.json` and left the `.cae`
  untouched, as documented.
* `optimize_hex_mesh.py`: run on a deliberately skewed sweep-hex mesh (2 Analysis Checks warnings).
  It moved 12 nodes in one pass and cleared both warnings (**2 -> 0**).
* `scratch_static_check.py`: see Fix 3. After the fix, the summed reaction was 3.7295467 N against a
  hand weight of 3.7295 N (quarter-plate volume x 7.85e-9 t/mm3 x 9810 mm/s2) - an exact match - with
  0 zero pivots and 0 numerical singularities.
* `shell_weld.py`: runs clean end to end on a synthetic touching-shell T-joint STEP (import ->
  imprint -> structured S4R mesh -> `PartFromMesh` + `mergeNodes` -> free-edge report), and its
  free-edge count of 88 is exactly the legitimate outer boundary of the open structure. But the
  imprint and merge branches did **not** fire, because Abaqus' own STEP export returns the joint
  already topologically stitched. **This script still needs a real CAD STEP file to be verified.**

### Fix 3 - `scratch_static_check.py` aborted in the pre-processor every time

`mdb.Model(objectToCopy=src)` copies the source model's BCs, loads, constraints, interactions and
output requests as well. The script then deletes all instances and builds its own assembly, so the
copied BCs still referenced assembly sets that no longer existed. Every run died with
`***ERROR: NODE SET ASSEMBLY_X0 HAS NOT BEEN DEFINED`, and because the failure was swallowed by a
bare `except`, the script printed a result block that merely omitted the numbers.

Three changes: strip `boundaryConditions`, `loads`, `predefinedFields`, `constraints`,
`interactions`, `fieldOutputRequests` and `historyOutputRequests` plus the assembly sets and
surfaces before rebuilding; create `F-Output-1` instead of assuming the copy has one; and report the
job status (read from the `.log` when `job.status` is `None`, which it is for a batch job in 2023)
plus a loud `ERROR:` line when the ODB cannot be read.

## 4. `abaqus-version-compat` - PARTIAL

Only Abaqus 2023 is installed on this machine, so the round trip was done **within** one release:
export from a 2023 `.cae`, rebuild in 2023, re-solve, compare.

| Check | Expected | Abaqus 2023 |
|---|---|---|
| `export_manifest.json` keywords | NODE, ELEMENT, MATERIAL, ELASTIC, STEP, STATIC, BOUNDARY, CLOAD | all present (28 keywords) |
| export files | `.inp` plus `.sat`/`.stp` per geometry part | `Cantilever.inp`, `Cantilever__BEAM.sat`, `Cantilever__BEAM.stp` |
| `rebuild_log.json` | status `ok`, 1 part, 1 step | ok, 1 part (orphan mesh), 1 step, 1 material |
| re-solved job | same tip deflection as the original | -0.381909 mm, RF2 = 1000 N: **identical** |
| `odb_upgrade.py --check` | reports "current format" | `current format, steps=['Load']` |
| `py23_check.py` on the builder scripts | 0 errors | 3 files, 0 errors, 0 warnings |

The manifest's `lost_by_route` section is accurate: the rebuilt model is an orphan mesh with no
geometry or feature history.

**Why PARTIAL, not PASS:** the thing this skill exists for - writing a deliverable in a newer release
that an older release can open - was not tested, because there is no second release here. Both
scripts behave correctly, but a 2023-to-2021 run could still hit keywords 2021 does not know. The
`references/version_matrix.md` guidance is unverified.

## 5. `abaqus-explicit-impact` - PASS

Example: 1 kg rigid sphere (R 25 mm) at 5 m/s onto a clamped 200 x 200 x 2 mm elastic-plastic steel
plate; 2 500 S4R plus 941 R3D4; general contact, friction 0.2; 3 ms.

| Quantity | Hand estimate | Abaqus 2023 | Error |
|---|---|---|---|
| initial kinetic energy ALLKE | 12 500 mJ | 12 500.013 mJ | **0.0001 %** |
| time to contact | 1.0e-4 s | consistent with the V3 history | - |
| stable time increment | 4-7e-7 s | 6.12e-7 s | in range |
| increments for 3 ms | 4 000-8 000 | 4 833 | in range |
| ETOTAL drift | about flat | 0.022 % of max energy | - |
| RP velocity V3 | -5 000 mm/s to a small positive rebound | -5 000 -> +2 424 mm/s | - |
| end-of-run energies | 12.5 J mostly plastic plus rebound KE | ALLPD 8 012, ALLSE 965, ALLKE 3 292, ALLAE 190 mJ | - |

`energy_balance.py --mode impact --ke0 12500`: **OVERALL PASS** - ke0 0.000 %, drift 0.022 %,
hourglass 2.09 %, damping 0.33 %, dmass 0 %, mass_work 0 %. Build 2 s, solve 23 s on 2 CPUs.

The 18 `.dat` warnings are all benign: "output request S/PEEQ/STATUS is not available for element
type R3D4/R3D3/MASS/ROTARYI", i.e. the field request also covers the rigid impactor and its point
mass, plus one note that hourglass control does not apply to the rigid elements.

### Fix 4 - the model could not be built at all: `RigidBody(surfaceRegion=...)`

`surfaceRegion=` is only for an **analytical** rigid surface. For the discrete rigid sphere Abaqus
raised *"The region corresponding to the analytical surface should belong to an analytical rigid part
instance"* and the build aborted. A discrete rigid part is tied to its reference point with
`bodyRegion=`. The same bug existed in `abaqus-forming-fld/scripts/build_dome_stretch.py` (Fix 6).

### Fix 5 - `energy_balance.py` read DMASS as a fraction, so its mass-scaling check was 100x out

`DMASS` in the ODB history is the **percentage** change of total model mass - the same number as the
`CHNG MASS` column of the `.sta`, confirmed against Abaqus 2023 - not a fraction. The check compared
it directly to a 0.02/0.05 limit, so the forming example's 279 % mass addition was reported as
`27907 %`. The verdict happened to be right (FAIL was correct), but the number was meaningless and a
genuinely mild 3 % mass addition would also have been reported as a 300 % failure. It is now divided
by 100.

## 6. `abaqus-heat-transfer` - PASS

Example: three-layer wall (brick / insulation / block, 100 mm each), Rsi 0.13, Rse 0.04, 20 degC
inside, 0 degC outside, 30 DC3D8 elements. Steady state.

| Quantity | Hand calculation | Abaqus 2023 | Error |
|---|---|---|---|
| q_mean | 5.958 W/m2 | 5.957677 W/m2 | **0.00 %** |
| U | 0.2979 W/m2K | 0.2978839 W/m2K | **0.00 %** |
| NT at x = 0 (inside surface) | 19.23 degC | 19.2255 degC | 0.00 % |
| NT at BRICK / INSULATION | 18.45 degC | 18.4518 degC | 0.01 % |
| NT at INSULATION / BLOCK | 1.43 degC | 1.4298 degC | 0.01 % |
| NT at x = 0.3 (outside surface) | 0.24 degC | 0.2383 degC | - |

Build 2 s, solve 12 s. `u_value.py` correctly volume-weighted by EVOL and reported `weighted_by:
EVOL`. A 1D linear-element model of a 1D problem matching the hand calculation to five digits is
what the example predicted.

The transient variant was built and solved too (24 h cycle, outside air swinging 0 -> 10 -> 0 degC,
`*Initial Conditions, type=TEMPERATURE` correctly written at 10 degC). It completes, and its
end-of-cycle flux (9.29 W/m2) is deliberately **not** the steady-state value, because the wall is
still releasing heat stored during the warm half of the day. The example README now says so, so
nobody reads it as a mismatch.

### Fix 6 - the JSON spec was silently ignored, and the script used its built-in defaults instead

Abaqus 2023 **strips the `--` separator** before the script sees `sys.argv`. Verified directly:

```
['...\ABQcaeK.exe', '-cae', '-noGUI', 'argvtest.py', '-lmlog', 'ON', '-tmpdir', '...',
 'slab_tr.json', 'submit']
```

`build_layered_slab.py` parsed its arguments as
`sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []`, so with no `--` present it got an
empty argument list, ignored the user's JSON file **without a word**, and silently built the default
textbook wall instead. That is the worst class of bug in this repository: it produces plausible
results for the wrong model. It now falls back to `sys.argv[1:]` and filters for `.json`, the same
way `build_from_spec.py` and `rebuild_from_inp.py` already did (which is why those two worked).

## 7. `abaqus-forming-fld` - PASS (mechanics only)

Example: quarter of a 200 mm diameter, 1 mm blank, flange locked beyond r = 80 mm, 100 mm rigid
hemispherical punch, generic power-law sheet (K = 500 MPa, n = 0.22), textbook FLC with FLC0 = 0.30.
2 395 S4R plus 6 613 R3D4; about 100 k increments; build 3 s, solve 3 min on 4 CPUs.

| Check | Expectation | Abaqus 2023 |
|---|---|---|
| initial yield printed by the build script | K x 0.005^0.22 = 156 MPa | 155.9 MPa |
| strain path at the pole, full disc | minor about equal to major | major 0.441, minor 0.403 (near equi-biaxial) |
| onset (FLDCRT >= 1) | before the full stroke | 53.66 mm of the 70 mm stroke, frame 26 |
| fracture (element deletion) | after onset | frame 29 for the strip case; same frame as onset for the full disc at 40 output intervals |
| punch force | collapses at failure | 15.6 kN -> 3.5 kN within two output frames |
| quasi-static (ALLKE/ALLIE, second half) | PASS or WARN | **PASS, 0.145 %** |
| `energy_balance.py --mode quasistatic` | PASS or WARN | **OVERALL PASS** |
| Considere (uniaxial) | FLC left side not far below n = 0.22 | FLC0 = 0.30 > 0.22 |

The documented strain-path series also behaves as claimed. Re-running with `STRIP_WIDTH = 50`:
minor strain at onset moves from **0.403 to -0.046** and major from **0.441 to 0.598** - the onset
point walks from the biaxial (right) side of the FLD toward plane strain and uniaxial (left), which
is the whole point of the Nakajima test series.

### Fix 7 - two defaults contradicted the documented result

* `DEPTH = 40.0` never reaches onset: at the full 40 mm stroke the criterion only gets to **0.645**,
  so `fld_extract.py` correctly reported `onset_frame: None` and the example's "FLDCRT reaches 1
  before the full 40 mm stroke" was simply wrong. Changed to `DEPTH = 70.0`, where onset lands at
  53.7 mm with room to see the post-necking collapse.
* `MASS_SCALING_DT = 5.0e-7` adds **about 280 % mass** on the default 2 mm seed (DMASS 279, which
  `energy_balance.py` FAILs once Fix 5 is in). The unscaled run needs only about 2.5x the increments
  (100 k instead of 40 k, 3 min instead of 1 min) and gives a 9.5 % higher peak punch force
  (15.6 kN vs 14.2 kN) while moving the onset stroke by only 0.2 % - so mass scaling here was
  measurably corrupting the force and buying very little. Changed to `None`.

Plus the `RigidBody(surfaceRegion=...)` fix from Fix 4, which applied here identically.

**What is still not verified:** the material and the FLC are illustrative. Everything above says the
*mechanics and the post-processing* work; none of it says the predicted forming limit is right for
any real steel. Replace both with measured data before using this on anything real.

---

## Fixes made, in one list

| # | File | Fix |
|---|---|---|
| 1 | `abaqus-model-builder/scripts/check_logs.py` | recognise `ANALYSIS DATACHECK COMPLETE` in the `.dat`: a datacheck writes no `.log`/`.sta`, so a clean one was reported as not completed and exited 1 |
| 2 | `abaqus-odb-extract/scripts/odb_extract.py` | `--region` with a node set on an integration-point field: retry at `ELEMENT_NODAL` instead of failing with `OdbError: Invalid component label` |
| 3 | `abaqus-mesh-doctor/scripts/scratch_static_check.py` | strip the copied BCs/loads/constraints/interactions/output requests and assembly sets before rebuilding the assembly (the job aborted in the pre-processor every time); create `F-Output-1` rather than assume it; report the real job status and shout when the ODB cannot be read |
| 4 | `abaqus-explicit-impact/scripts/build_drop_test.py` | `RigidBody(surfaceRegion=...)` -> `bodyRegion=` for a discrete rigid part (the build aborted) |
| 5 | `abaqus-explicit-impact/scripts/energy_balance.py` | DMASS is a percentage, not a fraction: divide by 100 (the check was 100x out) |
| 6 | `abaqus-heat-transfer/scripts/build_layered_slab.py` | Abaqus strips `--` from `sys.argv`, so the JSON spec was silently ignored and the built-in defaults were used instead |
| 7 | `abaqus-forming-fld/scripts/build_dome_stretch.py` | the same `RigidBody` fix; `DEPTH` 40 -> 70 mm (40 mm never reaches onset); `MASS_SCALING_DT` 5e-7 -> `None` (280 % added mass, 10 % error in punch force) |

All seven fixes keep the scripts valid on both kernels: 20 of 20 `.py` files byte-compile under the
Abaqus 2023 Python 2.7 kernel and under Python 3.12, and `py23_check.py` reports 0 errors and
0 warnings.

Note on `scripts/compile_check.sh`: it runs here but reports `FAIL (python3)` for every file, because
`python3` on this Windows host is the Microsoft Store stub rather than an interpreter. That is an
environment issue, not a repository one - the same files compile cleanly when `python` (3.12) and the
Abaqus 2.7 kernel are invoked directly. The script could be made more robust by rejecting a `python3`
that cannot run `-c 'pass'`.

Note on `scripts/scrub_check.sh`: it walks the whole repository folder, including git-ignored
scratch, so once you run an example inside the repo (as the documented workflow tells you to) it
fails on Windows user paths baked into Abaqus' own `.odb`, `.cae`, `.sat` and `.step` output.
Nothing committed here contains such a path - verified by scanning the staged diff - but the gate
should skip git-ignored files (for example by driving it from `git ls-files`) or it will keep crying
wolf.

## Remaining issues and what to test next

1. **Only Abaqus 2023.** Repeat all of the above on 2020-2022, 2024 and 2025. The 2024+ runs are the
   interesting ones: they use the Python 3.10 kernel, which nothing here has executed yet.
2. **The cross-release path is untested.** `export_for_older.py` -> `rebuild_from_inp.py` needs a
   genuine newer-to-older run before `abaqus-version-compat` can be called verified.
3. **`shell_weld.py` needs a real CAD STEP.** Its imprint and merge branches never fired on the
   synthetic test geometry.
4. **`build_from_spec.py` relies on its `--` fallback.** It works, but given that Abaqus strips `--`,
   the `argv.index('--')` branch is dead code on 2023 and should probably go.
5. **`shell`/`mergeNodes` and contact-force extraction** (`odb_extract.py --contact`) have only been
   seen on the graceful no-data path; no example in the repository requests CFN/CFS history.
6. **Mesh convergence.** Every result above is from one mesh. The cantilever and the wall are
   converged by construction; the Kt = 3.20 of the plate with a hole and the forming onset stroke are
   not mesh-converged and should not be quoted as mesh-independent.
