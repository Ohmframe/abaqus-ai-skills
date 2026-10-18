## What this changes

<!-- One or two sentences. Link the issue if there is one: "Closes #123". -->

## Type

- [ ] Fix to an existing skill, script or reference
- [ ] New skill
- [ ] Documentation only
- [ ] CI / tooling

## Tested how

<!-- Be exact and honest. "Not run in Abaqus" is a perfectly good answer. -->

- [ ] Not run in Abaqus (reviewed and lint-checked only)
- [ ] Run in Abaqus release: <!-- e.g. 2024 --> on <!-- OS -->, output summarised below
- [ ] Example result compared with the hand calculation in the example README

<!-- If you ran it, paste the summary lines (no confidential paths or data). -->

## Checklist

- [ ] `scripts/compile_check.sh` passes
- [ ] `scripts/scrub_check.sh` passes (with your own denylist, or `--no-denylist`)
- [ ] No confidential data: no client or employer names, geometry, material data, results, paths or e-mail addresses
- [ ] No binaries or results (`.cae`, `.odb`, `.jnl`, CAD, spreadsheets, PDFs)
- [ ] Scripts run on both Abaqus Python kernels (2.7 and 3.10): no f-strings, `print_function`, builtins restored
- [ ] New or changed skills keep the standard `SKILL.md` structure and an honest **Status** line
- [ ] New skills are listed in `README.md` and `AGENTS.md`
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
