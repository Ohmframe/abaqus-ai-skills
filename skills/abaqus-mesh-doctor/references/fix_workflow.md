# Mesh fix workflow

The order we follow when a model "won't mesh" or the job dies on element errors.

1. **Diagnose, don't touch** – run `mesh_diagnose.py` on the .cae. It lists invalid geometry,
   free edges, short edges, cells that cannot take the requested technique, and the bad
   elements grouped by cell with the edges and seeds involved. Fix the worst cell first.
2. **Geometry first**
   * invalid/imprecise geometry from CAD: `Part > Geometry Repair` (or `p.RepairInvalidEdges`,
     `p.RepairSmallEdges`, `p.RemoveRedundantEntities`), or re-export from CAD as STEP AP214.
   * edges shorter than about a third of the seed: virtual topology
     (`p.createVirtualTopology(ignoreRedundantEntities=True, mergeShortEdges=True, shortEdgeThreshold=...)`)
     or remove the feature in CAD.
   * shells from STEP with gaps: import with `stitchEdges`, then imprint contact lines and weld
     the mesh (`shell_weld.py`).
3. **Partition** until every cell is green/yellow (see `hex_partitioning.md`).
4. **Seed** critical edges by number (FIXED), then the global size. Re-mesh.
5. **Element type**: C3D8I for bending with few elements through thickness, C3D8R + enhanced
   hourglass for explicit, C3D10 (not C3D4) for tets, S4R for shells (S3 only as fill).
6. **Last resort for a few stubborn warnings**: `optimize_hex_mesh.py` relocates nodes while
   keeping them on the geometry. It does not survive a re-mesh.
7. **Constraints**: if a tie or coupling moves nodes ("adjust" ON) after meshing, it can recreate
   distorted elements. Untick `adjust` on ties next to a fine hex mesh and check the .dat.
8. **Prove it**: re-run Analysis Checks, then `scratch_static_check.py` (dummy linear solve):
   reaction = weight and no zero-pivot warnings means the mesh is connected and solvable.
9. **Document**: keep the mesh_report.json before and after with the model; it is the evidence
   for the reviewer.

## Symptoms -> first thing to check

| Symptom | First check |
|---|---|
| "The selected regions cannot be meshed with the current controls" | cell topology: partition or switch to sweep/tet |
| orange cell after a partition | sliver faces from the cut; move the cut to a feature |
| job: "elements have zero or negative volume" | invalid geometry or reversed sweep; run mesh_diagnose |
| job: "excessively distorted elements" mid-run | mesh too coarse at contact or material failure; not a pre-processing problem |
| zero pivot / numerical singularity on a shell model | unconnected panels: free element edges inside the structure |
| explicit runs 10x slower than expected | one tiny element: STABLE_TIME_INCREMENT check |
