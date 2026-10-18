---
name: Bug report
about: A skill, script or example did not work, or gave a wrong or misleading answer
title: "[bug] <skill-name>: <short summary>"
labels: bug
assignees: ""
---

<!--
Thanks for the report. Please do NOT attach .cae, .odb, CAD files or any confidential
model, client or employer data. A minimal, public reproduction (for example one of the
examples in this repository, or a small textbook-style model) is ideal.
-->

## Skill and file

- Skill: <!-- e.g. abaqus-model-builder -->
- File: <!-- e.g. scripts/build_from_spec.py -->

## Environment

- Abaqus release: <!-- e.g. 2023 HF3, 2024, 2025 -->
- Abaqus Python kernel: <!-- 2.7 (<= 2023) or 3.10 (2024+) -->
- OS: <!-- Windows 11, RHEL 8, ... -->
- AI tool (if any): <!-- Claude Code, Cursor, Codex, Gemini CLI, ChatGPT, none -->

## What you ran

```bash
# the exact command, e.g.
abaqus cae noGUI=build_from_spec.py -- spec.json
```

## What happened

<!-- Error message, traceback, or the relevant lines from .log / .sta / .msg / .dat.
     Remove paths, user names and anything else that identifies you or your project. -->

```text

```

## What you expected

<!-- e.g. the hand-calculation value from the example README, a clean datacheck, ... -->

## Anything else

<!-- Workarounds you found, release-specific API differences, suggestions. -->
