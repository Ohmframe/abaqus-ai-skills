# ODB API notes (odbAccess)

```python
from odbAccess import openOdb
import abaqusConstants as C
odb = openOdb(path='Job.odb', readOnly=True)
step = odb.steps['Load']                 # odb.steps.keys() in step order
fr = step.frames[-1]                     # fr.frameValue = step time (or frequency for modal)
S = fr.fieldOutputs['S']
mises = S.getScalarField(invariant=C.MISES)
s11 = S.getScalarField(componentLabel='S11')
sub = S.getSubset(region=odb.rootAssembly.instances['BEAM-1'])        # or an element set
nod = fr.fieldOutputs['U'].getSubset(region=odb.rootAssembly.nodeSets['RP_TIP'])
for v in mises.values: v.data, v.elementLabel, v.nodeLabel, v.instance.name, v.position
reg = step.historyRegions['Assembly ASSEMBLY']                        # energies
ke = reg.historyOutputs['ALLKE'].data                                 # ((t, value), ...)
odb.close()
```

## Things that trip people up

- **Names are upper-case in the ODB.** An instance `Beam-1` is `BEAM-1`, and a set `RP_tip` is `RP_TIP`.
  `odb_extract.py` looks names up case-insensitively.
- **Assembly sets made on geometry** (faces, edges) are written to the ODB as node *and* element
  sets with the same name. Part-level sets live on the instance: `inst.nodeSets[...]`.
- **History region names** are `Node <INSTANCE>.<label>` for nodes and `Node ASSEMBLY.<n>` for
  reference points. Energies are under `Assembly ASSEMBLY`. Map a set to its regions by node label
  (`nodeset_region_names()`); never hard-code a label.
- **RP history output is in global axes**, even when the BC that drives the RP uses a local csys.
  Project U, RF and CF onto your direction yourself.
- **Contact force history is written twice per pair** (`CFN1 A/B` and `CFN1 B/A`). De-duplicate before
  you sum (`--contact` does).
- **Shell and beam output has several section points.** A plain max over `values` mixes top and
  bottom faces. Fine for a peak, wrong for a membrane value. Use `getSubset(sectionPoint=...)` if you
  need one face.
- **Integration-point vs nodal values.** Stresses are at integration points by default. Contour plots
  in CAE show averaged nodal values, so a CAE legend max and a script max can differ by a few
  percent. Say which one you report.
- **Element deletion.** Deleted elements still carry their last values. Filter with `STATUS` > 0.5
  before you take a max (`abaqus-forming-fld` does this).
- **Element volume (EVOL)** must be requested as field output. Use it for volume-weighted averages
  on unstructured meshes (heat flux, U-values) instead of assuming a regular grid.
- **Speed.** `.values` builds a Python object per value. For millions of values use
  `fo.bulkDataBlocks` (numpy arrays) or restrict with `getSubset` first.
- **Older ODBs** must be upgraded before a newer release can open them for writing. Use
  `isUpgradeRequiredForOdb` / `upgradeOdb` (see `abaqus-version-compat`).
- **Licences.** `abaqus python` uses no CAE token. `abaqus cae noGUI=` does. Extract with `abaqus python`.
