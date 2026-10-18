# Abaqus heat transfer notes

## Elements and steps
* Pure conduction: DC3D8 / DC3D4 / DC2D4 (heat-transfer elements, temperature DOF 11 only).
  Coupled temperature-displacement: C3D8T and a CoupledTempDisplacementStep.
* Steady state: `HeatTransferStep(response=STEADY_STATE)`; time is nominal, loads ramp.
* Transient: `response=TRANSIENT`, `deltmx` = max temperature change per increment (2-5 °C typical),
  initial temperatures as a predefined field in Initial. Small first increments with second-order
  elements can give spurious oscillations: refine the mesh or use linear elements near the boundary.

## Boundary conditions
* Film (convection): `m.FilmCondition(name=, createStepName=, surface=, definition=EMBEDDED_COEFF,
  filmCoeff=h, sinkTemperature=T)`.
  Combined convection + radiation surface resistances (Rsi/Rse) map to h = 1/Rs.
* Radiation to ambient: `m.RadiationToAmbient(name=, createStepName=, surface=, radiationType=AMBIENT,
  distributionType=UNIFORM, emissivity=, ambientTemperature=)` needs
  `model.setValues(absoluteZero=-273.15, stefanBoltzmann=5.670374e-8)` in SI.
* Prescribed temperature: `TemperatureBC`. Heat flux: `SurfaceHeatFlux`. Internal generation: `BodyHeatFlux`.
* Time-varying sink: TabularAmplitude with `sinkTemperature=1.0, sinkAmplitude=...`.

## Outputs and post-processing
* Request NT (nodal temperature), HFL (heat flux vector), RFL (reaction flux at prescribed-T nodes), EVOL.
* U-value of a detail: volume-averaged HFL over the full build-up / dT (u_value.py). For a thermal
  bridge, compare with the 1D U of the same build-up: the difference x length is the linear
  thermal transmittance psi.
* Energy check: the sum of RFL (or the film heat flow) at inside and outside must balance in steady state.

## Pitfalls
* Units: in mm-t-s (energy in mJ, power in mW) k keeps the SI number (mW/(mm K) = W/(m K)),
  but h becomes h_SI x 1e-3 (mW/(mm² K)), rho becomes rho_SI x 1e-12 (t/mm³) and cp becomes
  cp_SI x 1e6 (mJ/(t K)). Easy to get wrong: use SI metres for building physics.
* `absoluteZero` unset with radiation -> nonsense; set it even if radiation is added later.
* Films on internal faces between layers (from partitions) are not boundaries: select outer faces only.
* Contact conductance between parts needs `ThermalConductance` in the contact property; a tie is perfect contact.
