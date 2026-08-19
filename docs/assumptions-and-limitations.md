# Assumptions and limitations

Themis is research software for controlled coordination experiments. It is not suitable for operational conjunction assessment, maneuver design, spacecraft command, regulatory compliance, or flight-safety decisions.

## Physical and risk model

- Closed-loop scenarios use deterministic `LinearTrajectory` objects in a local benchmark frame. They do not use SGP4, two-body dynamics, perturbations, frames, covariance propagation, orbit determination, or ephemeris uncertainty.
- The separate optional propagation module can read TLEs and use Skyfield/SGP4, but it is not connected to closed-loop maneuver execution.
- A conjunction means Euclidean separation below a fixed threshold at sampled discrete steps. Risk is not collision probability and has no covariance model.
- Maneuvers are instantaneous velocity-vector changes at an integer step. There are no burns, attitude constraints, windows, or navigation updates.
- Fuel cost equals delta-v magnitude in benchmark units. Mission disruption is a fixed linear proxy. Neither represents mass, propellant, or monetary cost.

## Knowledge and communication

- Physical truth is exact within the model. There is no sensor noise, stale state estimate covariance, clock drift, or adversarial input.
- Risk alerts originate from a ground-truth monitor. Centralized protocols receive global views; decentralized protocols receive beliefs populated by delivered alerts.
- Latency is a fixed integer number of simulation steps. Packet loss is independent seeded Bernoulli loss. Bandwidth is a per-sender message-count cap, not bytes, topology, link budget, contention, or routing.

## Time, execution, and safety

- `spacecraft-coordination-v1` still detects initial risk at step zero and performs one proposal/reassessment pass. Campaign v1 repeats discrete integer cycles; neither is continuous or real-time operations.
- Execution failure is seeded Bernoulli failure. Magnitude error is a deterministic positive scaling applied equally to vector components; direction and timing error are omitted.
- The validator checks modeled constraints only. Acceptance is not evidence of real-world safety. Secondary-risk scanning is limited to configured objects, threshold, and short discrete horizon.

## Determinism

The network and executor use controlled `random.Random` instances seeded from the experiment. Candidate ordering, protocol registration, event sequencing, and run IDs are deterministic. Model-derived decisions, events, and metrics should repeat for identical resolved config, seed, and software version on supported Python versions. Wall-clock runtime, artifact timestamp, filesystem path, and git metadata are observational exceptions. Floating-point behavior may differ across future Python/platform implementations.

Campaign v1 strengthens this with separately derived scenario, network, and execution streams. An added draw in one source does not shift another source's sequence.

## Input and product limits

- Closed-loop config supports built-in or explicit linear initial states, not an arbitrary TLE/source-data path. The optional TLE demo is separate.
- Replay is ordered trace inspection, not state rehydration.
- Sweeps are local and sequential. The built-in analysis provides descriptive mean/t-interval summaries only; there is no parallel scheduler, hypothesis-testing framework, power analysis, or correction for multiple comparisons.
- The artifact-driven viewer visualizes only recorded or explicitly labeled derived facts. It does not improve physical fidelity, reconstruct omitted state, or explain causality with a learned model.
- Version 0.4 is an alpha public interface. The project is distributed under the Apache License 2.0; API stability is still limited by its pre-1.0 status.

Campaign auctions use exact delivered snapshots, configurable heuristic weights, one bid reservation per participant, and a fixed round schedule. They do not model strategic behavior, truthful incentives, combinatorial allocation, cryptography, settlement, or operational markets. A `SECONDARY` label is causal only inside this deterministic model; it is not a real-world causal estimate.
