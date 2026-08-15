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

- The current lifecycle detects initial risk at step zero and performs one proposal and reassessment pass. `duration_steps` is not a continuous operations campaign.
- Execution failure is seeded Bernoulli failure. Magnitude error is a deterministic positive scaling applied equally to vector components; direction and timing error are omitted.
- The validator checks modeled constraints only. Acceptance is not evidence of real-world safety. Secondary-risk scanning is limited to configured objects, threshold, and short discrete horizon.

## Determinism

The network and executor use controlled `random.Random` instances seeded from the experiment. Candidate ordering, protocol registration, event sequencing, and run IDs are deterministic. Model-derived decisions, events, and metrics should repeat for identical resolved config, seed, and software version on supported Python versions. Wall-clock runtime, artifact timestamp, filesystem path, and git metadata are observational exceptions. Floating-point behavior may differ across future Python/platform implementations.

## Input and product limits

- Closed-loop config supports built-in or explicit linear initial states, not an arbitrary TLE/source-data path. The optional TLE demo is separate.
- Replay is ordered trace inspection, not state rehydration.
- Sweeps are local and sequential. There is no parallel scheduler or statistical analysis layer.
- There is no visualization UI. Saved artifacts are suitable for a future decoupled viewer.
- Version 0.1 is an alpha public interface. The project currently has no declared open-source license, which must be resolved before unrestricted redistribution.
