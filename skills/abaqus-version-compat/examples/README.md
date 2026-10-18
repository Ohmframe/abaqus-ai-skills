# Worked example: take the cantilever back to an older release

**Verified on Abaqus 2023 (same-release round trip):** the rebuilt model reproduces the original exactly, -0.381909 mm and RF2 1000 N; the cross-release step is not yet tested.

Uses the cantilever from `abaqus-model-builder/examples/cantilever_beam.json`.

```bash
# --- in the NEWER release (say 2025) ---
abaqus cae noGUI=../../abaqus-model-builder/scripts/build_from_spec.py -- cantilever_beam.json
abaqus cae noGUI=../scripts/export_for_older.py -- Cantilever.cae out:cantilever_export
#   -> cantilever_export/Cantilever.inp, Cantilever__BEAM.sat/.stp, export_manifest.json

# --- in the OLDER release (say 2021) ---
abaqus cae noGUI=../scripts/rebuild_from_inp.py -- cantilever_export out:cantilever_2021.cae
python ../scripts/py23_check.py ../../abaqus-model-builder/scripts   # will the builder run there?
```

Better: the builder script itself runs on 2.7 and 3, so in the older release simply run
`build_from_spec.py` with the same JSON. You get native geometry, partitions and sets.

## What you should see

| Check | Expected |
|---|---|
| `export_manifest.json` -> models[0].keywords | includes `NODE`, `ELEMENT`, `MATERIAL`, `ELASTIC`, `STEP`, `STATIC`, `BOUNDARY`, `CLOAD` |
| rebuild_log.json | status `ok`, 1 part (orphan mesh), 1 step |
| job from the rebuilt model | same tip deflection as the original (≈ 0.38 mm, see the model-builder example) |

## Result on Abaqus 2023 (verified, same-release round trip)

| Check | Expected | Abaqus 2023 |
|---|---|---|
| `export_manifest.json` -> models[0].keywords | NODE, ELEMENT, MATERIAL, ELASTIC, STEP, STATIC, BOUNDARY, CLOAD | **all present**, 28 keywords |
| export files | `.inp` plus `.sat`/`.stp` per part | **Cantilever.inp, Cantilever__BEAM.sat, Cantilever__BEAM.stp** |
| `rebuild_log.json` | status `ok`, 1 part, 1 step | **ok, 1 part (orphan mesh), 1 step, 1 material** |
| job from the rebuilt model | same tip deflection as the original | **-0.38191 mm, RF2 = 1000 N: identical** |
| `odb_upgrade.py --check` on a 2023 ODB | "current format" | **current format, steps=['Load']** |
| `py23_check.py` on the builder scripts | 0 errors | **3 files, 0 errors, 0 warnings** |

The export was rebuilt in the **same** release (only Abaqus 2023 was available). The cross-release
step (export in a newer release, rebuild in an older one) is the next test; until then, confirm
with a datacheck in the target release.
