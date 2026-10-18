# Contributing

Thanks for helping improve Abaqus AI Skills by OhmFrame. We welcome bug reports, test results from real
Abaqus releases, fixes and new skills.

Please follow our [Code of Conduct](CODE_OF_CONDUCT.md). Report security issues privately as described in
[SECURITY.md](SECURITY.md), not in a public issue. Use the issue templates (bug report, new skill) and the
pull request template; they ask for the details we need.

## Most useful right now

* **Run an example** in your Abaqus release and report the outcome (release, OS, the command, the summary
  lines, and whether it matched the hand calculation in the example README).
* API differences between releases (keyword renames, changed defaults) with the release numbers.

## Ground rules

1. **No confidential data.** Never commit client or employer geometry, material data, results, names,
   paths, e-mail addresses or credentials. Examples must be textbook-style problems with public values.
2. **No binaries or results**: no `.cae`, `.odb`, `.jnl`, CAD files, spreadsheets or PDFs. Scripts must
   rebuild everything.
3. **Generic scripts**: parameters at the top or in a JSON spec; no hard-coded project values.
4. **Both Python kernels**: code must run on Abaqus Python 2.7 and 3.10. No f-strings; use
   `from __future__ import print_function`; restore `sum/min/max/abs/round` after `from abaqus import *`.
5. **Fail loudly**: an empty selection or a missing set stops the script with a clear message.
6. **Say what is tested**: state in the README or docstring whether a script was run in Abaqus, in which release.

## Before you open a pull request

```bash
scripts/compile_check.sh                  # py_compile (python3, and python2 if installed) + py23 linter + bash -n
scripts/scrub_check.sh /path/to/denylist  # with your own list of terms that must never appear
scripts/scrub_check.sh --no-denylist      # or: e-mail, path and file checks only (what CI runs)
```

CI (`.github/workflows/ci.yml`) runs `yamllint`, `compile_check.sh` and `scrub_check.sh` in CI mode
(`SCRUB_SKIP_DENYLIST=1`) on every push and pull request. The CI runners have no Python 2.7, so the
2.7 byte-compile only runs where a `python2` interpreter is on `PATH`; the py23 linter always runs.
The only e-mail addresses allowed in the repository are the generic OhmFrame role addresses
(`conduct@`, `security@`, `noreply@`); the scrub check fails on any other address.

Add a line under `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md) for user-visible changes.

## Adding a skill

```
skills/<skill-name>/
  SKILL.md        # YAML frontmatter: name, description with a clear "Use when ..." trigger
  scripts/        # generic, parameterised
  references/     # checklists, API notes, pitfalls
  examples/       # a small public worked example + README with the hand calculation
```

Every `SKILL.md` uses the same structure, in this order:

1. Frontmatter: `name` (equal to the folder name) and `description` (what it does, then
   "Use when ..." with the phrases a user would actually type; under 1024 characters).
2. `# Title`, then a **Status** note naming the Abaqus release(s) the worked example was verified on
   and its key result against the hand calculation. A new skill that has not been run in Abaqus yet
   says so until it has. Claim only what was run.
3. `## When to use` (including "Not for: ..." pointers to other skills), `## Files`, `## Workflow`,
   `## Checks before you report`, `## Rules`, `## References`, `## Background`.

Keep `SKILL.md` short: the workflow and rules. Put long material in `references/`. State units explicitly.
Add the new skill to the table in `README.md` and to the index in `AGENTS.md`.
Write skills tool-neutrally: plain Markdown and scripts, so they work in Claude Code and as
instructions or context in other AI tools.

## Licence

By contributing you agree that your contribution is released under the MIT licence of this repository.
