# JSON spec for `build_from_spec.py`

The top-level keys are listed in build order. Lengths are in your unit system; `units` is declared
for the sanity check and the manifest. Validate a spec with `python scripts/validate_spec.py spec.json`
before you spend a CAE token.

| Key | Type | Notes |
|---|---|---|
| `model_name` | str | Model name in the `.cae`. Also the default job name. |
| `units` | str | `mm-N-tonne-s-MPa`, `m-N-kg-s-Pa` or `in-lbf-lbfs2in-s-psi`. Used for the density check. |
| `workdir` | str | Output folder. Defaults to the spec's folder. |
| `cae_name` | str | `.cae` file name without extension. Defaults to `model_name`. |
| `parts` | list | See *parts* below. |
| `materials` | list | `name`, plus optional `density`, `elastic` [E, nu], `plastic` [[stress, plastic strain], ...], `conductivity`, `specific_heat`, `expansion`. |
| `sections` | list | `name`, `type` `solid` or `shell`, `material`, `thickness` (shell), `int_points` (shell, default 5). |
| `section_assignments` | list | `part`, `section`, optional `set` name. Assigns the whole part. |
| `mesh` | list | See *mesh* below. |
| `instances` | list | `name`, `part`, optional `rotate` {`axis_point`, `axis_dir`, `angle`}, then `translate` [dx, dy, dz]. Rotation is applied first. |
| `reference_points` | list | `name`, `point`. Creates an RP and an assembly set with the same name. |
| `sets` | list | `name`, `instance`, `kind` (`faces`, `edges`, `vertices`, `cells`, `nodes`, `elements`), `bbox` [xmin, ymin, zmin, xmax, ymax, zmax], optional `tol`. An empty pick aborts the build. |
| `surfaces` | list | `name`, `instance`, `bbox`, `side` (`side1`, `side2`, `both`). |
| `couplings` | list | `name`, `control` (RP set), `surface` (surface or set), `type` (`KINEMATIC` or `DISTRIBUTING`). |
| `steps` | list | Created in order. See *steps* below. |
| `amplitudes` | list | `name`, `type` (`smooth_step` or `tabular`), `data` [[t, a], ...]. |
| `bcs` | list | `name`, `type`, `set`, `step` (default `Initial`), DOFs `u1`..`ur3`, optional `amplitude`. Types: `encastre`, `pinned`, `xsymm`, `ysymm`, `zsymm`, `displacement`, `velocity`, `temperature` (`magnitude`). In `Initial`, a listed DOF means fixed. |
| `loads` | list | `concentrated_force` (`set`, `cf1..3`), `pressure` (`surface`, `magnitude`), `gravity` (`vector`), `surface_heat_flux` (`surface`, `magnitude`). Each needs a `step`. |
| `predefined` | list | `velocity` (`set`, `vector`) or `temperature` (`set`, `magnitude`). Applied in Initial. |
| `interactions` | list | `tie` (`main`, `secondary`, `position_tolerance`, `adjust`), `general_contact` / `general_contact_explicit` (`friction`, optional `pairs` [[surfA, surfB], ...]; default is All* self), `film` (`surface`, `film_coeff`, `sink_temperature`, `step`). |
| `outputs` | dict | `field` {`variables`, `num_intervals`}, `energies` [ALLKE, ...] (sets H-Output-1), `history` [{`name`, `step`, `set`, `variables`, `num_intervals` or `frequency`}]. |
| `absolute_zero` | float | Default -273.15 when any heat step exists. |
| `job` | dict | `name`, `cpus`, `double` (true for DOUBLE_PLUS_PACK explicit precision). |

## parts

| `type` | Fields | Result |
|---|---|---|
| `box` | `size` [dx, dy, dz] | Solid. The rectangle (0,0)-(dx,dy) in XY is extruded dz along +Z. |
| `rect_shell` | `size` [dx, dy] | Planar shell in XY. |
| `plate_with_hole` | `size` [dx, dy], `hole_radius`, optional `hole_center`, `thickness` | Solid if `thickness` is given, otherwise a shell. |
| `cylinder` | `radius`, `length` | Solid along +Z. |
| `polygon` | `points` [[x, y], ...], optional `thickness` | Closed polygon: extruded solid, or a shell. |
| `step` | `file`, optional `combine` | STEP import (`scaleFromFile=OFF`). The builder warns on invalid geometry. |

Every part can have `partitions`: a list of `{"type": "principal_plane", "plane": "YZ", "offset": 250}`
or `{"type": "three_points", "points": [[..], [..], [..]]}`. Each partition cuts all cells (or all
faces, for shells).

## mesh

`part`, `seed` (global size), optional `elem_shape` (`HEX`, `TET`, `QUAD`, `TRI`, `WEDGE`),
`technique` (`STRUCTURED`, `SWEEP`, `FREE`), `elem_codes` (for example `["C3D8R"]` or
`["C3D8R", "C3D6", "C3D4"]`), `library` (`STANDARD` or `EXPLICIT`), `hourglass` (`ENHANCED`),
`deviation_factor`, `min_size_factor`, and `edge_seeds` [{`bbox`, `number` or `size`}].
A part that ends up with 0 elements aborts the build. The builder prints Analysis Checks error and
warning counts for every part.

## steps

| `type` | Fields |
|---|---|
| `static` | `nlgeom`, `time_period`, `initial_inc`, `max_inc`, `min_inc`, `max_num_inc`, `stabilize` (dissipated energy fraction, for example 2e-4) |
| `frequency` | `num_eigen` |
| `explicit` | `time_period`, `mass_scaling_dt` (semi-automatic, only elements below the target), `restart_intervals` |
| `heat_steady` | none |
| `heat_transient` | `time_period`, `initial_inc`, `min_inc`, `max_inc`, `deltmx` |

Don't mix Explicit and Standard steps in one model. Make two models (or two specs) instead.
