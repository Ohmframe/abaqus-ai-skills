---
name: abaqus-mesh-doctor
description: Diagnose and fix Abaqus meshes - Analysis Checks errors and warnings, orange (unmeshable) cells, distorted or negative-volume elements, free edges in shell models imported from STEP, and partitioning for structured or swept hex meshes. Use when an Abaqus part will not mesh, a job stops on element or mesh errors, a shell assembly is not connected (zero pivots, free edges), or the user wants a clean hex mesh or a mesh-quality report.
---

# Abaqus mesh doctor

> **Status: untested.** The scripts and workflow in this skill have not been run in Abaqus yet.
> Treat every report and fix as unverified until the checks below pass, and tell the user so.

Get an Abaqus mesh from "won't mesh / job dies" to a solvable mesh with evidence.
Diagnose first, change second, prove last.

## When to use

* "The selected regions cannot be meshed with the current controls", orange cells, a part that only
  meshes with tets.
* Analysis Checks errors or warnings; "elements have zero or negative volume" at the start of a job.
* Shell models from CAD (STEP) with free edges, unwelded panels, zero pivots or numerical singularities.
* A structured or swept hex mesh is wanted (partitioning strategy).
* Not for: "excessively distorted elements" late in a run from contact or material failure (that is a
  modelling problem; see `abaqus-model-builder` and `abaqus-explicit-impact`).

## Files

| Path | Run with | Purpose |
|---|---|---|
| `scripts/mesh_diagnose.py` | `abaqus cae noGUI=mesh_diagnose.py -- model.cae model:NAME part:NAME [export]` | Read-only report: geometry checks, free/short edges, mesh controls per cell, Analysis Checks and shape metrics, bad elements grouped by cell, shell edge-sharing histogram. Writes `mesh_report.txt/.json`; `export` also writes SAT/STEP. |
| `scripts/optimize_hex_mesh.py` | `abaqus cae noGUI=optimize_hex_mesh.py -- cae:model.cae model:M part:P out:new.cae` | Clears leftover hex warnings by moving nodes on the geometry (`editNode(projectToGeometry=ON)`). Lost on re-mesh. |
| `scripts/shell_weld.py` | `abaqus cae noGUI=shell_weld.py -- step:in.step out:out.cae seed:S` | STEP shells that only touch: imprinted contact lines, matched structured S4R mesh, `PartFromMesh` + `mergeNodes`, free-edge report before and after |
| `scripts/scratch_static_check.py` | `abaqus cae noGUI=scratch_static_check.py -- cae:model.cae model:M part:P axis:x units:SI_m` | Throw-away linear solve on a copy with dummy properties: max U, reaction vs weight, zero-pivot count |
| `examples/plate_hole_hex.py` | `abaqus cae noGUI=plate_hole_hex.py [-- submit]` | Worked example: butterfly partition, structured C3D8I mesh, Kt check against the hand calculation |

## Workflow

1. **Ask / find**: which `.cae`, model and part; element family wanted (hex, tet, shell); solver
   (Standard or Explicit); the region of interest.
2. **Diagnose**: run `mesh_diagnose.py`. Read `mesh_report.txt` top to bottom and quote the counts to
   the user. Do not edit the model yet.
3. **Fix geometry** (repair, virtual topology, stitch): `references/fix_workflow.md`.
4. **Partition for hex**: `references/hex_partitioning.md`. Write partitions as script lines (points at
   features, bounding boxes), not GUI clicks, so they can be re-run. Re-find entities after every cut.
5. **Seed and mesh**: critical edges by number with `constraint=FIXED`, equal counts on opposite edges,
   then the global size. Run `verifyMeshQuality(criterion=ANALYSIS_CHECKS)` after each change.
6. **Shell assemblies from CAD**: `shell_weld.py`, then inspect the `FREE_EDGE_NODES` set.
7. **Polish** remaining warnings with `optimize_hex_mesh.py`, only once the mesh is final.
8. **Prove**: re-run `mesh_diagnose.py` (before/after table) and `scratch_static_check.py`.
9. **Report** errors and warnings before -> after, the element count and type, and every remaining
   warning with the reason it is acceptable (`references/quality_criteria.md`).

## Checks before you report

* Analysis Checks errors = 0; warnings in the region of interest = 0, or explained.
* Element types as intended (no unintended tets or wedges in a hex region).
* Shells: no free element edges inside the structure; T-junctions only where intended.
* `scratch_static_check.py`: reaction equals the applied weight and no zero-pivot warnings, i.e. the
  mesh is connected and solvable.
* A mesh this skill touched still needs a mesh-convergence check on the real job.

## Rules

* Never overwrite the user's `.cae`: save under a new name (`out:`) and keep the original.
* Run scripts with `abaqus cae noGUI=` (needs a CAE licence token); arguments go after `--`. The GUI
  equivalent is File > Run Script.
* Face and edge indices change after every partition: select by coordinates or bounding box.
* An empty selection (`findAt` miss, empty bounding box) must stop the script, not continue.
* Element choice: C3D8I for bending with few elements through the thickness, C3D8R with enhanced
  hourglass control for Explicit, C3D10 (not C3D4) for tets, S4R for shells (S3 only as fill).
* Scripts run on Abaqus Python 2.7 (2023 and older) and 3.10 (2024 and newer).

## References

* `references/fix_workflow.md`: the order of fixes and a symptom -> first-check table.
* `references/hex_partitioning.md`: structured/sweep rules, butterfly (O-grid) cuts, partition API calls.
* `references/quality_criteria.md`: Analysis Checks vs Verify Mesh shape metrics, what matters.
* `examples/README.md`: plate with a hole (Kirsch/Heywood hand values, reaction check).
* Related skills: `abaqus-model-builder`, `abaqus-explicit-impact` (stable time increment).

## Background

Distilled from OhmFrame production work on thin-walled shell assemblies imported from STEP (free edges,
unwelded panels) and on repairing solid models whose hex mesh failed Analysis Checks. Only the
generalised fixes are included; no project geometry or data.
