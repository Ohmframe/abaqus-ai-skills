# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
