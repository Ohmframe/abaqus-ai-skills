# Forming limit (FLD) analysis in Abaqus

## Concepts
* **FLC** (forming limit curve): major vs minor in-plane strain at necking onset, measured on a test
  series (Nakajima: hemispherical punch on strips of different widths, or flat-bottom punch tests).
  Left side (minor < 0) uniaxial/drawing, FLC0 at plane strain (minor = 0), right side biaxial.
* Abaqus `FldDamageInitiation(table=((major, minor), ...))` evaluates the criterion
  FLDCRT = current major / FLC major at the current minor strain. FLDCRT >= 1 = necking predicted.
* The FLC is strain-path dependent: it is valid for (near) linear strain paths. For strongly
  non-linear paths consider a stress-based limit (FLSD, `FlsdDamageInitiation`) or MSFLD.
* `DamageEvolution(type=ENERGY, table=((Gf,),))` softens after initiation; with `elemDeletion=ON` the element is
  removed when the degradation reaches `maxDegradation`. Results after onset are mesh dependent: use onset
  (FLDCRT = 1) as the engineering answer, deletion only as a qualitative fracture indicator.

## Model checklist
- [ ] Shell elements S4R with 5+ section points; seed ~ 1-2 x sheet thickness in the dome region.
- [ ] Measured hardening to large strain (extrapolate with Swift/Voce and say so).
- [ ] FLC in true (log) strain, same convention as LE.
- [ ] Friction value for the lubricant system (0.02-0.1 lubricated, 0.1-0.2 dry); it moves the failure location.
- [ ] Quasi-static check: ALLKE/ALLIE < 5-10 % (energy_balance.py --mode quasistatic), DMASS small.
- [ ] Symmetry only if the strain path and the expected failure are symmetric.

## Post-processing
* `fld_extract.py` gives the onset frame, punch stroke/force at onset and fracture, and major/minor strain
  per element at onset. Plot minor (x) vs major (y) with the FLC on top; points above the curve have failed.
* Report the limit dome height (punch stroke at onset) for comparison with tests: this is the usual validation
  quantity for Nakajima-type tests.
* In the CAE viewer: Result > Field Output > FLDCRT, and the FLD plot (Tools > XY Data > forming limit), or
  plot the CSV.

## Abaqus calls
```python
mat.FldDamageInitiation(table=((0.60, -0.30), (0.45, -0.15), (0.30, 0.0), (0.35, 0.15)))
mat.fldDamageInitiation.DamageEvolution(type=ENERGY, table=((10.0,),))
mesh.ElemType(elemCode=S4R, elemLibrary=EXPLICIT, elemDeletion=ON, maxDegradation=0.99)
# field output: 'LE', 'PEEQ', 'STATUS', 'SDEG', 'DMICRT'  (DMICRT writes FLDCRT for this criterion)
```
