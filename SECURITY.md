# Security policy

## Reporting a vulnerability

Please **do not open a public GitHub issue** for security problems.

E-mail **security@ohmframe.com** with:

* the affected file(s) and version or commit,
* a description of the issue and its impact,
* steps to reproduce, if you have them.

We will acknowledge your report, keep you informed while we work on a fix, and agree the disclosure
timing with you. We will credit you in the changelog if you wish.

## Scope

This repository contains Markdown instructions and Python/Bash scripts that an AI agent or a user runs
locally with a separately licensed Abaqus installation. Relevant reports include, for example:

* a script that could overwrite or delete files outside its working folder,
* unsafe handling of input files (for example evaluating untrusted content as code),
* instructions in a `SKILL.md` that could lead an agent to run unsafe commands,
* confidential data accidentally committed to the repository.

Problems in Abaqus itself should go to Dassault Systèmes / SIMULIA support, not to us.

## Supported versions

Only the latest release on the default branch is supported.

## A reminder on running scripts

Scripts in this repository have **not been run in Abaqus** yet (see the README status). Review any
script, and anything an AI agent writes or changes, before you run it on your machine or your models.
Keep copies of your `.cae` and `.odb` files.
