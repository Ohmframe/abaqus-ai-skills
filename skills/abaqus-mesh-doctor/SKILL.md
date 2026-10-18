---
name: abaqus-mesh-doctor
description: Diagnose and fix Abaqus meshes - Analysis Checks errors/warnings, orange (unmeshable) cells, distorted or negative-volume elements, free edges in STEP shell models, and partitioning for structured/sweep hex. Use when an Abaqus part will not mesh, a job stops on element errors, a shell model is not connected, or the user wants a clean hex mesh or a mesh-quality report.
---

# Abaqus mesh doctor

OhmFrame workflow for getting an Abaqus mesh from "won't mesh / job dies" to a verified,
solvable mesh. Diagnose first, change second, prove last.

## Scripts (all generic, untested on Abaqus by OhmFrame unless stated)

| Script | Run with | What it does |
|---|---|---|
| `scripts/mesh_diagnose.py` | `abaqus cae noGUI=mesh_diagnose.py -- model.cae model:NAME part:NAME [export]` | Read-only report: geometry checks, free/short edges, mesh controls per cell, Analysis Checks + shape metrics, bad elements grouped by cell, shell edge-sharing histogram. Writes `mesh_report.txt/.json`; `export` also writes SAT/STEP. |
| `scripts/optimize_hex_mesh.py` | `abaqus cae noGUI=optimize_hex_mesh.py -- cae:model.cae model:M part:P out:new.cae` | Clears leftover hex warnings by relocating nodes on the geometry (`editNode(projectToGeometry=ON)`). Lost on re-mesh. |
| `scripts/shell_weld.py` | `abaqus cae noGUI=shell_weld.py -- step:in.step out:out.cae seed:S` | STEP shells that only touch -> imprinted contact lines, matched structured S4R mesh, `PartFromMesh` + `mergeNodes`, free-edge report before/after. |
| `scripts/scratch_static_check.py` | `abaqus cae noGUI=scratch_static_check.py -- cae:model.cae model:M part:P axis:x units:SI_m` | Throw-away linear solve on a copy with dummy properties: max U, reaction vs weight, zero-pivot count. |
| `examples/plate_hole_hex.py` | `abaqus cae noGUI=plate_hole_hex.py [-- submit]` | Worked example: butterfly partition -> structured C3D8I mesh, Kt check against hand calc. |

## Workflow

1. **Ask / find**: which .cae, model, part; element family wanted (hex, tet, shell); solver
   (Standard or Explicit); the region of interest.
2. **Diagnose**: run `mesh_diagnose.py`. Read `mesh_report.txt` top to bottom; quote the counts
   to the user. Do not edit the model yet.
3. **Fix geometry** (repair, virtual topology, stitch) - see `references/fix_workflow.md`.
4. **Partition for hex** - see `references/hex_partitioning.md`. Write the partitions as script
   lines (findAt points at features), not GUI clicks, so they can be re-run. Re-find entities
   after every cut.
5. **Seed and mesh**: critical edges by number with FIXED, opposite edges equal counts, then the
   global size. Use `verifyMeshQuality(criterion=ANALYSIS_CHECKS)` after each change.
6. **Shell assemblies from CAD**: `shell_weld.py`, then inspect `FREE_EDGE_NODES`.
7. **Polish** remaining warnings with `optimize_hex_mesh.py` only when the mesh is final.
8. **Prove**: re-run `mesh_diagnose.py` (before/after table) and `scratch_static_check.py`.
   Report errors/warnings before -> after, the element count and any warnings that remain and why
   they are acceptable (`references/quality_criteria.md`).

## Rules

* Never overwrite the user's .cae: save to a new name (`out:`) and keep the original.
* Run scripts with `abaqus cae noGUI=` (needs a CAE licence token); the GUI equivalent is
  File > Run Script. Arguments go after `--`.
* Indices of faces/edges change after every partition: select by coordinates or bounding box.
* An empty selection (`findAt` miss, empty bounding box) must stop the script, not continue.
* For Abaqus 2023 and older the kernel is Python 2.7: no f-strings. These scripts run on both.
* Results from a mesh this skill touched still need a mesh convergence check on the real job.

## Lessons behind this skill

Built from OhmFrame production work on a thin-walled aerospace shell assembly imported from
STEP (free edges, unwelded spars and ribs) and on repairing a solid model whose hex mesh
failed Analysis Checks in a customer-supplied .cae. The generalised fixes are in the scripts;
no project geometry or data is included.
