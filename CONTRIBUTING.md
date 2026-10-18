# Contributing

Thanks for helping improve Abaqus AI Skills by OhmFrame. We welcome bug reports, test results from real
Abaqus releases, fixes and new skills.

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
scripts/scrub_check.sh /path/to/denylist  # optional: your own list of terms that must never appear
```

## Adding a skill

```
skills/<skill-name>/
  SKILL.md        # YAML frontmatter: name, description with a clear "Use when ..." trigger
  scripts/        # generic, parameterised
  references/     # checklists, API notes, pitfalls
  examples/       # a small public worked example + README with the hand calculation
```

Keep `SKILL.md` short: the workflow and rules. Put long material in `references/`.
Add the new skill to the table in `README.md` and to the index in `AGENTS.md`.
Write skills tool-neutrally: plain Markdown and scripts, so they work in Claude Code and as
instructions or context in other AI tools.

## Licence

By contributing you agree that your contribution is released under the MIT licence of this repository.
