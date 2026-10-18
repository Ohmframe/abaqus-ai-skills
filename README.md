# OhmFrame Abaqus skills for Claude Code

Open-source [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills) that teach an AI
coding agent how to work with **Abaqus** the way we work at OhmFrame: build models by script,
run them in batch, read the logs, prove the mesh, check the energy balance and extract the numbers.

Each skill is a folder with a `SKILL.md` (when to use it and the workflow), generic `scripts/`
(parameters at the top or a JSON spec, never project data), `references/` (checklists, API notes,
pitfalls) and a small textbook-style worked example with hand calculations.

## Skills

| Skill | Use it when |
|---|---|
| [`abaqus-model-builder`](skills/abaqus-model-builder/SKILL.md) | creating or automating an Abaqus model (parts, materials, sections, assembly, steps, contact/ties, BCs, loads, mesh, job) from a JSON spec; running jobs from the command line; working out why a job failed from .log/.sta/.msg/.dat |
| [`abaqus-odb-extract`](skills/abaqus-odb-extract/SKILL.md) | getting numbers out of an .odb: field max/min with location, reaction sums, histories, energies, contact forces -> CSV + summary.json |
| [`abaqus-mesh-doctor`](skills/abaqus-mesh-doctor/SKILL.md) | a part will not mesh, Analysis Checks errors/warnings, STEP shell models with free edges, partitioning for structured/sweep hex |
| [`abaqus-version-compat`](skills/abaqus-version-compat/SKILL.md) | a .cae/.odb must open in an older release, ODB upgrades, scripts that must run on Python 2.7 (<= 2023) and 3 (2024+) |
| [`abaqus-explicit-impact`](skills/abaqus-explicit-impact/SKILL.md) | drop tests, impactor hits, vehicle/mass impacts, quasi-static pull-out or crush in Explicit, energy-balance checks |
| [`abaqus-heat-transfer`](skills/abaqus-heat-transfer/SKILL.md) | steady/transient conduction through layered build-ups, film boundaries, U-values |
| [`abaqus-forming-fld`](skills/abaqus-forming-fld/SKILL.md) | sheet forming limits: dome-stretch models, FLD damage, necking onset, FLD strain points |

## Install

Copy the skill folders you want into your personal or project skills directory:

```bash
git clone <this repository> ohmframe-sim-skills
# personal (all projects)
mkdir -p ~/.claude/skills && cp -r ohmframe-sim-skills/skills/* ~/.claude/skills/
# or per project
mkdir -p .claude/skills && cp -r ohmframe-sim-skills/skills/* .claude/skills/
```

Claude Code picks a skill up from its `description` when your request matches ("build an Abaqus model of...",
"why did my job abort", "get the max Mises out of this odb", "make this .cae open in 2021").
Many of the scripts are also useful on their own from the command line.

## Requirements

* A **licensed Abaqus installation** (Abaqus/CAE for `abaqus cae noGUI=` scripts, the solver for jobs).
  Nothing here includes or provides licences, solvers or SIMULIA software.
* The scripts are written for both Abaqus Python kernels: 2.7 (Abaqus 2023 and older) and 3.10 (2024 and newer).
* Helpers that do not touch Abaqus (`check_logs.py`, `validate_spec.py`, `py23_check.py`) run on any Python 2.7/3.
* Bash for the `.sh` helpers (Linux, macOS, WSL or Git Bash on Windows).

## Status: what is and is not verified

* Every `.py` file byte-compiles under Python 2.7 and Python 3 and passes our Python-2/3 and Abaqus-API
  linter (`scripts/compile_check.sh`).
* The plain-Python helpers (log checker, spec validator, linter, energy-balance logic) were exercised on
  synthetic inputs.
* The workflows, API patterns and pitfalls come from production Abaqus projects that OhmFrame has delivered.
  **The generic scripts in this repository have not yet been run end-to-end in Abaqus.** Each example README lists
  the hand calculation the result should match; please open an issue with your release and the output if it does not.

## Disclaimer

These skills and scripts are provided "as is" (MIT licence). Finite element results depend on modelling
choices, input data and engineering judgement. **You are responsible for verifying every result**
(hand calculations, mesh convergence, energy balance, test data) before you use it for design, certification or
any decision. AI agents make mistakes: review what they generate.

## Built by OhmFrame

We are OhmFrame, an engineering simulation studio (FEA, CFD, scripting and automation).
These skills are a distilled version of how we deliver Abaqus work.

**Need it done for you?** Model building, debugging a failing job, mesh repair, explicit impact, thermal or
forming studies, or custom Abaqus automation for your team: **[ohmframe.com](https://ohmframe.com)**.

## Contributing

Issues and pull requests are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

[MIT](LICENSE) © OhmFrame
