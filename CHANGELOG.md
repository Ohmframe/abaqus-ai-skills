# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-10-18

### Verified

- **All seven skills verified on Abaqus 2023** (Standard, Explicit and CAE; Python 2.7 kernel): every
  worked example run end to end and compared with its hand calculation. Details: [`TEST_REPORT.md`](TEST_REPORT.md).
  - model-builder: cantilever tip deflection -0.38191 mm vs -0.384 mm (0.5 %), RF2 1000.00 N (0.00 %).
  - odb-extract: reproduces every cantilever value; field, reaction, history and energy paths exercised.
  - mesh-doctor: plate with hole Kt 3.20 vs 3.14 Heywood (1.9 %), RF1 -50 000 N (0.00 %).
  - version-compat: same-release round trip identical (partial; cross-release path not yet tested).
  - explicit-impact: drop test initial KE 12 500.01 vs 12 500 mJ, energy balance PASS.
  - heat-transfer: wall U 0.297884 vs 0.29788 W/m2K (0.00 %).
  - forming-fld: necking onset at 53.7 mm, quasi-static PASS (mechanics; material illustrative).

### Fixed (7 script bugs found in the Abaqus 2023 run)

1. `check_logs.py`: a clean `datacheck` (no `.log`/`.sta`) was reported as not completed.
2. `odb_extract.py`: `--region` with a node set on an integration-point field crashed; now retries at `ELEMENT_NODAL`.
3. `scratch_static_check.py`: copied BCs/loads referenced deleted sets, so every run aborted; also reports the real job status.
4. `build_drop_test.py`: `RigidBody(surfaceRegion=)` -> `bodyRegion=` for a discrete rigid part (the build aborted).
5. `energy_balance.py`: `DMASS` is a percentage, not a fraction (the mass-scaling check was 100x out).
6. `build_layered_slab.py`: Abaqus strips `--` from `sys.argv`, so the JSON spec was silently ignored.
7. `build_dome_stretch.py`: the same `RigidBody` fix; defaults `DEPTH` 40 -> 70 mm and `MASS_SCALING_DT` 5e-7 -> `None`.

### Changed

- Documentation: README badge "verified: Abaqus 2023", new Validation section with per-skill results,
  status notes in `AGENTS.md`, every `SKILL.md` and example `README.md` updated to the verified results.
- `scripts/scrub_check.sh`: inside a git work tree it scans only files git knows about (tracked plus
  untracked, not ignored), so git-ignored example runs no longer trip the gate.

### Known limits

- Abaqus 2024+ (Python 3.10 kernel) not yet tested; cross-release path of `abaqus-version-compat`
  untested; `shell_weld.py` imprint/merge awaits a real CAD STEP; forming material and FLC
  illustrative; plate Kt and forming onset from a single mesh.

## [0.1.0] - 2026-10-18

First public release, published before the Abaqus validation run (see 0.2.0).

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

[Unreleased]: https://github.com/Ohmframe/abaqus-ai-skills/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Ohmframe/abaqus-ai-skills/releases/tag/v0.2.0
[0.1.0]: https://github.com/Ohmframe/abaqus-ai-skills/tree/77c4eb6
