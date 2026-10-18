# Abaqus scripting pitfalls we have hit

Each item below cost us real time on a past project. Every one is easy to avoid once you know it.

## Python and the kernel

1. **Python version.** Abaqus 2023 and older run Python 2.7. Abaqus 2024 and newer run Python 3.10.
   Write code that runs on both: no f-strings, `from __future__ import print_function`,
   `//` for integer division, and `open(path, 'w')` for text.
2. **`json` returns `unicode` in Python 2.7.** Convert names to `str` before you pass them to the
   API, or some calls reject them (`to_str()` in `build_from_spec.py`).
3. **`from abaqus import *` shadows built-ins.** `sum`, `min`, `max`, `abs` and `round` get replaced.
   Restore them from `builtins` (Py3) or `__builtin__` (Py2) straight after the import.
4. **Don't reuse `abaqusConstants` names for your own variables.** A flag called `EXPLICIT` broke
   `elemLibrary=EXPLICIT`. Use `IS_EXPLICIT`, `USE_STANDARD` and the like.
5. **Don't name your modules after Abaqus modules**: `part.py`, `mesh.py`, `job.py`, `step.py`,
   `load.py`, `material.py`, `section.py`, `assembly.py`, `interaction.py`.
6. **`mdb.openStep` exists only after `from caeModules import *`.**
7. **Model repositories appear only when their modules are loaded.** On a model read from a `.cae`,
   `m.fieldOutputRequests` raises `AttributeError` until you `import step, interaction, load, mesh, job`.
8. **`print` under `cae noGUI=` can vanish.** Write to `sys.__stdout__` and flush it.
9. **Script arguments go after a bare `--`.** `sys.argv` also carries the launcher's own flags, so
   pick arguments by pattern (for example `*.json`), not by position.
10. **Licence tokens.** `abaqus cae noGUI=` uses a CAE token. `abaqus python` doesn't. Do ODB
    post-processing with `abaqus python`.

## API changes and keyword quirks

11. **`main`/`secondary` (2022+) vs `master`/`slave` (2021 and older)** for `Tie`,
    `SurfaceToSurfaceContactStd/Exp` and friends. Some 2023 docstrings still say master/slave, but
    the kernel rejects those keywords. `tie()` in `build_from_spec.py` tries both.
12. **The element-deletion keyword is `elemDeletion`**, not `elementDeletion`. Pass it only when you
    need it (Explicit with damage).
13. **Assembly set names must not equal `<instance>_<part set>`**, or they collide with the names
    Abaqus generates.
14. **A `*CONTACT PAIR` can't use a double-sided shell surface that contains T-junctions** (web/flange).
    Split it into one pair per side, or use a node set as the secondary.
15. **A history output request takes only one interaction.** Make one request per contact pair.
16. **Contact history is written twice per pair** (`A/B` and `B/A`) with identical values. If you sum
    every CFN series, you double the force. De-duplicate on the sorted pair name (`abaqus-odb-extract`
    does this).
17. **Non-structural mass** lives at `rootAssembly.engineeringFeatures.NonstructuralMass(...)`. The
    per-area unit constant is `MASS_PER_AREA`.
18. **An mdb can't be left with zero models.** Create or import your model first, then delete `Model-1`.

## Model content

19. **`mdb.saveAs` stores whatever is in the mdb at that moment.** If you replace a steady step with a
    transient one and then save, the `.cae` holds only the transient model. Keep one model per
    analysis and name each model after its analysis.
20. **Deleting a step also deletes everything created in it**: BCs, loads, film conditions and
    output requests. Rebuild them from parameters, not from memory.
21. **An imported `.inp` gives orphan-mesh parts**: no geometry and no feature tree. Reviewers may
    reject it ("doesn't look modelled in Abaqus"). Build native parts when the `.cae` is the deliverable.
22. **Job names don't reliably describe a deck.** Grep `*Element, type=` and `*Contact` in the `.inp`
    before you conclude which variant a result came from.
23. **Don't re-pick node sets by hand.** A different box-pick changes the coupling region, which
    changes stiffness and peak stress. Save sets in the `.cae` and reuse them by name.
24. **Reference-point history output is in GLOBAL axes**, even when the BC uses a local csys. Project
    U/RF/CF onto your local direction in post-processing.
25. **Tie tolerance and `adjust`.** Pick a position tolerance that catches only nodes that really touch.
    The "will not be tied" warnings are then expected. Switch `adjust` OFF on faceted or curved
    surfaces. With it on, we once saw thousands of nodes pulled onto a faceted surface and dozens of
    distorted elements.
26. **Shell offsets.** With MIDDLE_SURFACE shells, the contact face sits half a thickness from the
    reference surface. Include that half-thickness in initial gaps (indenter clearance, platens).
27. **Laminate Poisson's ratio.** Abaqus `LAMINA` wants the MAJOR ratio nu12. Papers sometimes print
    the minor ratio; convert with nu12 = nu21 * E1 / E2.
28. **Heat transfer in degrees C needs `absoluteZero=-273.15`.** Set it in physical constants (the builder
    sets it automatically for heat steps).
29. **Units.** Pick one consistent system: mm-N-tonne-s-MPa gives a steel density of 7.85e-9. Meshes from
    CT or STL can arrive in micrometres. Check the bounding box before you trust a stress value.
    The builder warns when a density looks wrong for the declared units.
30. **Check placement after every rotate/translate.** Compare each instance's bounding range with the
    expected one and abort the build if it's off. A 120 deg rotation about (1,1,1) maps the local axes
    cyclically (x->y->z->x). That's handy, but easy to get wrong.

## Running jobs

31. **Long runs from an agent shell.** When the tool shell times out, the solver gets SIGTERM. Launch
    long jobs detached (`nohup ... &` or `Start-Process`) and poll the `.sta`. Lost licence servers
    (nightly network resets) kill jobs the same way, so don't schedule long runs across them.
32. **Explicit restart.** Without `step.Restart(numberIntervals=N, overlay=ON)`, a killed explicit run
    can't be resumed.
33. **Paths with spaces.** Run each job from its own folder and pass `scratch=` with a path that has no
    spaces.
34. **More than 300,000 explicit increments.** Run in double precision (`double=both`) to avoid
    round-off.
35. **Learning Edition.** It has a 1000-node model limit. Check `NUMBER OF NODES` in the `.dat`.
36. **When you stop background work**, make sure you kill the right `ABQcaeK`/`standard`/`explicit`
    process. An idle GUI's CPU time doesn't change.

## Interpreting results

37. **Compare like with like.** A linear-elastic stress criterion predicts crack *initiation*. A test
    machine records *peak load*. These match for a thin tube in axial compression and differ widely
    for a ring in diametral compression.
38. **Always do a hand check.** Beam theory, EA/L, 1D thermal resistance. On every past project, the
    hand check caught at least one set-up or units error early.
39. **Put the quantity and unit in every image file name** (`..._HFL_W_per_m2.png`). A heat-flux legend
    reading 1449 was once read as 1449 deg C.
40. **Regenerate reports after any re-run.** Decks and tables go stale silently.
