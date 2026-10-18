---
name: New skill or skill improvement
about: Propose a new Abaqus skill, or a new workflow, check or script for an existing one
title: "[skill] <skill-name>: <short summary>"
labels: enhancement
assignees: ""
---

<!--
Please keep this public: no client or employer names, geometry, material data or results.
-->

## The task an engineer (or agent) is trying to do

<!-- e.g. "fatigue post-processing from an .odb", "submodelling workflow", "cohesive-zone delamination" -->

## Proposed skill

- Name: <!-- abaqus-<topic>, lower-case with hyphens -->
- Trigger ("Use when ..."): <!-- the sentence an agent should match on -->
- New skill or extension of: <!-- e.g. extends abaqus-odb-extract -->

## Workflow outline

1.
2.
3.

## Checks the skill must make before a result is reported

<!-- hand calculation, equilibrium, energy balance, mesh convergence, ... -->

## Public worked example

<!-- A textbook-style problem with a closed-form or published answer that the example README can use. -->

## Abaqus specifics

- Releases you can test on:
- Keywords / API calls involved:
- Known release differences:

## Can you contribute it?

- [ ] I can write the `SKILL.md`
- [ ] I can write or adapt the scripts
- [ ] I can run the example in Abaqus and report the output
