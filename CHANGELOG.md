# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Verified

- **All seven worked examples now run end to end on Abaqus 2023** (Windows) and match their hand
  calculations. Full numbers, run times and fixes: [`TEST_REPORT.md`](TEST_REPORT.md). Headlines:
  cantilever tip deflection -0.38191 mm vs -0.384 mm (0.5 %) with RF2 = 1000.00 N; plate with hole
  Kt = 3.20 vs the 3.0-3.14 hand range with RF1 = -50 000 N; drop test ALLKE0 = 12 500.01 mJ vs
  12 500 mJ; wall U = 0.297884 vs 0.29788 W/m2K; dome-stretch necking onset at 53.7 mm with the
  quasi-static and energy checks passing.
- Status lines in `README.md` and in every `SKILL.md` and example `README.md` updated accordingly.
  Abaqus 2020-2022, 2024 and 2025 remain untested, as does the cross-release path in
  `abaqus-version-compat` and the imprint/merge path of `shell_weld.py`.

### Fixed

- `abaqus-explicit-impact/scripts/build_drop_test.py` and
  `abaqus-forming-fld/scripts/build_dome_stretch.py`: `RigidBody(surfaceRegion=...)` only accepts an
  analytical rigid surface, so neither model could be built at all. Discrete rigid parts are tied to
  their reference point with `bodyRegion=`.
- `abaqus-heat-transfer/scripts/build_layered_slab.py`: Abaqus strips the `--` separator from
  `sys.argv`, so the script silently ignored the user's JSON spec and built its default wall instead.
- `abaqus-mesh-doctor/scripts/scratch_static_check.py`: the model copy kept the original BCs, loads,
  constraints and output requests, which referenced assembly sets the script then deleted; every run
  aborted in the pre-processor with "NODE SET ... HAS NOT BEEN DEFINED" and the failure was swallowed.
  Also reports the real job status now.
- `abaqus-odb-extract/scripts/odb_extract.py`: `--region` with a node set on an integration-point
  field (S, E, PEEQ) failed with `OdbError: Invalid component label`; it now retries at
  `ELEMENT_NODAL` and explains the mismatch if that is empty too.
- `abaqus-explicit-impact/scripts/energy_balance.py`: `DMASS` is a percentage, not a fraction, so the
  mass-scaling check was out by a factor of 100.
- `abaqus-model-builder/scripts/check_logs.py`: a `datacheck` run writes no `.log` or `.sta`, so a
  clean datacheck was reported as "not completed" and exited 1.

### Changed

- `abaqus-forming-fld/scripts/build_dome_stretch.py` defaults: `DEPTH` 40 -> 70 mm (at 40 mm the FLD
  criterion only reaches 0.65, so the documented onset never happens) and `MASS_SCALING_DT` 5e-7 ->
  `None` (5e-7 added about 280 % mass and softened the peak punch force by about 10 %).

## [0.1.0] - 2026-10-18

First public release. **Nothing in this release has been run in Abaqus yet**; every skill is marked
untested.

### Added

- Seven Abaqus agent skills in the `SKILL.md` format, each with scripts, references and a worked
  example with hand calculations:
  `abaqus-model-builder`, `abaqus-odb-extract`, `abaqus-mesh-doctor`, `abaqus-version-compat`,
  `abaqus-explicit-impact`, `abaqus-heat-transfer`, `abaqus-forming-fld`.
- `AGENTS.md` index so agents that read `AGENTS.md` (and Cursor, Gemini CLI, ChatGPT and others) can
  use the same skills as instructions or context.
- `scripts/compile_check.sh`: byte-compile every script with Python 3 (and Python 2.7 when installed),
  Python 2/3 and Abaqus-API linter, `bash -n` on shell scripts.
- `scripts/scrub_check.sh`: confidentiality gate (external denylist, e-mail addresses, Windows paths,
  forbidden file types), with a CI mode (`--no-denylist` or `SCRUB_SKIP_DENYLIST=1`) that runs the
  regex and file checks without the denylist.
- GitHub Actions CI: YAML lint, compile check and scrub check (CI mode) on every push and pull request.
- README with quick start, skills table, illustrative example, roadmap and FAQ; banner at
  `docs/assets/banner.svg`.
- Community files: `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `SECURITY.md`, `CONTRIBUTING.md`,
  issue templates (bug report, new skill) and a pull request template.

[Unreleased]: https://github.com/Ohmframe/abaqus-ai-skills/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Ohmframe/abaqus-ai-skills/releases/tag/v0.1.0
