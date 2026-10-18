# Abaqus AI Skills by OhmFrame

**Teach your AI coding agent to build, run, debug and post-process Abaqus models the way simulation engineers do.**

AI agent skills for **Abaqus**: seven focused skill packs that give an AI assistant the workflow,
scripts and hard-won pitfalls for real Abaqus work. Build models by script, run them in batch,
read the logs, prove the mesh, check the energy balance and extract the numbers.

The skills use the `SKILL.md` format, which [Claude Code](https://docs.claude.com/en/docs/claude-code/skills)
loads natively. The same files are plain Markdown plus Python, so they also work as instructions or
context in other agents: Cursor rules, Codex and other tools that read `AGENTS.md`, ChatGPT / custom GPT
knowledge files, and Gemini CLI context files (see [Use with other AI tools](#use-with-other-ai-tools)).

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

## Install (Claude Code)

Copy the skill folders you want into your personal or project skills directory:

```bash
git clone https://github.com/ohmframe/abaqus-ai-skills.git
# personal (all projects)
mkdir -p ~/.claude/skills && cp -r abaqus-ai-skills/skills/* ~/.claude/skills/
# or per project
mkdir -p .claude/skills && cp -r abaqus-ai-skills/skills/* .claude/skills/
```

Claude Code picks a skill up from its `description` when your request matches ("build an Abaqus model of...",
"why did my job abort", "get the max Mises out of this odb", "make this .cae open in 2021").
Many of the scripts are also useful on their own from the command line.

## Use with other AI tools

Only Claude Code reads the `SKILL.md` frontmatter as a skill natively. Every other tool below uses the
same files as ordinary instructions or context. The content is identical; only the loading differs.
Tool features change often: check each tool's current documentation.

* **Agents that read `AGENTS.md`** (for example OpenAI Codex, and Cursor in the project root): copy or
  clone this repository into your project (for example as `abaqus-ai-skills/`) and keep the root
  [`AGENTS.md`](AGENTS.md). It indexes the skills and tells the agent which `SKILL.md` to open for which task.
  Alternatively, paste the index into your own project's `AGENTS.md` and fix the relative paths.
* **Cursor rules**: create one rule per skill in `.cursor/rules/` (for example `abaqus-model-builder.mdc`),
  use the skill's `description` as the rule description so it is applied when relevant, and paste the
  `SKILL.md` body, or reference the file with `@` mentions in chat. Keep the `scripts/` and `references/`
  folders in the project so the paths in the skill resolve.
* **Gemini CLI**: Gemini CLI loads `GEMINI.md` context files and can import other Markdown files with
  `@path` lines. Either add `@./abaqus-ai-skills/AGENTS.md` (or individual `SKILL.md` files) to your
  `GEMINI.md`, or set `"context": {"fileName": ["AGENTS.md", "GEMINI.md"]}` in `.gemini/settings.json`.
* **ChatGPT / custom GPTs**: upload the relevant `SKILL.md` and `references/*.md` files (and scripts you want
  reviewed or adapted) as knowledge files or chat attachments, and put the skill's workflow in the GPT's
  instructions. ChatGPT cannot run your Abaqus installation: it can write and review scripts and interpret
  logs or CSV output you paste back; run the scripts yourself.
* **Any other assistant**: paste the `SKILL.md` of the task at hand into the conversation or system prompt,
  and attach the referenced scripts. Everything is plain text.

In every case the scripts run on **your** machine with **your** Abaqus licence; the AI only writes,
adapts and reads them.

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

## Trademarks

Abaqus is a trademark of Dassault Systèmes. This project is not affiliated with or endorsed by Dassault Systèmes.
Other product names are trademarks of their respective owners and are used only to describe compatibility.

## Built by OhmFrame

We are OhmFrame, an engineering simulation studio (FEA, CFD, scripting and automation).
These skills are a distilled version of how we deliver Abaqus work.

**Need it done for you?** Model building, debugging a failing job, mesh repair, explicit impact, thermal or
forming studies, or custom Abaqus automation for your team: **[ohmframe.com](https://ohmframe.com)**.

## Contributing

Issues and pull requests are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

[MIT](LICENSE) © OhmFrame
