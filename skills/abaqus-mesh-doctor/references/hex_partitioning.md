# Partitioning for hex meshes

Abaqus can mesh a cell with hex elements STRUCTURED or SWEEP only when its topology allows it.
The Mesh module colours each cell: **green** = structured, **yellow** = sweep, **orange** = not
meshable with the current element shape (tet or partition needed), **pink** = free.
The job is to cut the geometry into blocks until every cell is green or yellow.

## Rules of thumb

1. **Structured** needs every face of the cell to be 3-5 sided (ideally 4) with matching
   opposite edges. A cube-like block is the target shape.
2. **Sweep** needs a source face, a target face with the same topology, and side faces that
   connect them (an extrusion or revolve path). Holes through the sweep direction are fine.
3. Cut at **geometric features**: fillet tangency lines, hole centres, changes of section, rib
   roots. Partitions placed off-feature make skewed elements.
4. **Holes and bosses**: use the butterfly (O-grid) pattern. Either diagonal cuts from the hole
   to the outer corners (quarter model: one cut), or an inner square/ring around the hole plus
   diagonal cuts from its corners. The ring keeps the elements next to the hole square.
5. **T-junctions and ribs**: extend the rib faces through the base plate (PartitionCellByExtendFace)
   so the base becomes blocks under the rib and blocks between ribs.
6. **Curved thin walls**: partition through the thickness only where needed; sweep along the
   wall with 2+ elements through the thickness (4+ for bending with linear elements, or use C3D8I).
7. **Mesh order matters** for dependent instances: seed the critical edges (hole arcs, contact
   faces) by number with constraint FIXED first, then the global seed.
8. Opposite edges in a structured block need the **same element count**. If you bias one edge,
   bias its opposite with the same number (not size).

## Abaqus calls we use

| Goal | Call |
|---|---|
| plane through 3 points | `p.PartitionCellByPlaneThreePoints(cells=, point1=, point2=, point3=)` |
| plane by point and normal | `p.PartitionCellByPlanePointNormal(cells=, point=, normal=)` (normal is an edge or datum axis) |
| extend an existing face | `p.PartitionCellByExtendFace(cells=, extendFace=)` |
| sweep a sketch | `p.PartitionCellBySweepEdge(...)` |
| imprint a line on a face | `p.PartitionFaceByShortestPath(faces=, point1=, point2=)` |
| project edges onto a face | `p.PartitionFaceByProjectingEdges(faces=, edges=, extendEdges=True)` |
| check a technique | `p.setMeshControls(regions=, elemShape=HEX, technique=STRUCTURED)` then `p.getMeshControl(region=cell, attribute=TECHNIQUE)` |

Each partition renumbers faces and edges. Re-find entities with `findAt`/`getByBoundingBox`
after every cut; never reuse stored indices.

## When to stop partitioning

* Hex in the region of interest, tets (C3D10) elsewhere tied with `*TIE` is a legitimate answer
  for very complex castings. Make sure the tie surfaces are not in the stress hot spot.
* If a cut produces sliver faces (< 1/10 of the seed), undo it and move the cut: slivers become
  the worst elements in the mesh.
