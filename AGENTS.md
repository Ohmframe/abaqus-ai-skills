# AGENTS.md: Abaqus AI Skills by OhmFrame

This repository holds skills for working with the Abaqus finite element software. Each skill is a
folder under `skills/` with a `SKILL.md` (when to use it, the workflow, the rules), `scripts/`,
`references/` and `examples/`. All paths below are relative to this file.

**Status: verified on Abaqus 2023 (v0.2.0).** Every skill's worked example has been run end to end on
Abaqus 2023 and matched its hand calculation; per-skill results are in the README's Validation section
and `TEST_REPORT.md`. Abaqus 2024+ (Python 3 kernel) and the cross-release path of
`abaqus-version-compat` are not yet tested. On the user's own model, always run the skill's checks and
say which Abaqus release the result comes from.

## How to use this index

1. Match the user's task to a skill in the table below.
2. Open and follow that skill's `SKILL.md` before writing or running anything. Every `SKILL.md` has
   the same sections: When to use, Files, Workflow, Checks before you report, Rules, References,
   Background. Open its `references/` files when the `SKILL.md` points to them.
3. Prefer the skill's scripts over writing new code; adapt the parameters or JSON spec, not the logic.
4. Several skills can apply (for example, build a model with `abaqus-model-builder`, then extract results with
   `abaqus-odb-extract`).

| Skill | Open | Use when |
|---|---|---|
| abaqus-model-builder | `skills/abaqus-model-builder/SKILL.md` | creating or scripting an Abaqus model (parts, materials, sections, assembly, steps, contact/ties, BCs, loads, mesh, job) from a JSON spec; running jobs from the command line; diagnosing failed jobs from .log/.sta/.msg/.dat |
| abaqus-odb-extract | `skills/abaqus-odb-extract/SKILL.md` | getting numbers from an .odb: field max/min with location, reaction sums, histories, energies, contact forces, CSV/JSON output |
| abaqus-mesh-doctor | `skills/abaqus-mesh-doctor/SKILL.md` | a part will not mesh, Analysis Checks errors/warnings, distorted elements, STEP shell models with free edges, partitioning for structured/sweep hex |
| abaqus-version-compat | `skills/abaqus-version-compat/SKILL.md` | a .cae/.odb must open in an older Abaqus release, ODB upgrades, scripts that must run on Python 2.7 (Abaqus <= 2023) and Python 3 (2024+) |
| abaqus-explicit-impact | `skills/abaqus-explicit-impact/SKILL.md` | Abaqus/Explicit drop tests, impacts, quasi-static pull-out or crush, mass scaling, stable increment, hourglassing, energy-balance checks |
| abaqus-heat-transfer | `skills/abaqus-heat-transfer/SKILL.md` | steady or transient conduction, film/radiation boundaries, layered build-ups, U-values and heat flux |
| abaqus-forming-fld | `skills/abaqus-forming-fld/SKILL.md` | sheet-forming limits, FLD/FLC damage initiation, necking onset, dome-stretch models, FLDCRT post-processing |

## Rules that apply to every skill

* Abaqus runs on the user's machine with the user's licence. Run scripts as
  `abaqus cae noGUI=script.py -- args` (model building, needs a CAE licence token) or
  `abaqus python script.py args` (ODB post-processing). If you cannot execute commands, give the user the
  exact commands and ask for the output.
* Write Abaqus scripts that run on both Python 2.7 and Python 3: no f-strings,
  `from __future__ import print_function`, restore `sum/min/max/abs/round` after `from abaqus import *`.
  Check with `python skills/abaqus-version-compat/scripts/py23_check.py <file>`.
* Never overwrite the user's .cae or .odb; save to a new name.
* Never present a result without its check: hand calculation, reaction balance, mesh check or energy balance
  as described in the skill. The scripts are verified on their worked examples (Abaqus 2023); a user's
  model still needs its own checks.
* Keep the user's project data out of shared files and out of this repository.

Before committing changes to this repository run `scripts/compile_check.sh` and `scripts/scrub_check.sh`
(see `CONTRIBUTING.md`).

Abaqus is a trademark of Dassault Systèmes. This project is not affiliated with or endorsed by Dassault Systèmes.
