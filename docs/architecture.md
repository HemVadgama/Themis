# Architecture

Themis separates decision policy from physical truth so protocol comparisons do not accidentally grant one policy control over simulation state.

```text
Validated TOML configuration
             │
             ▼
ScenarioConfig + initial LinearTrajectory objects
             │
             ▼
WorldState (authoritative simulated truth)
             │
             ├── Conjunction detector creates RiskEvent objects
             │
             ├── NetworkSimulator carries alerts with seeded loss/latency
             │
             ▼
Agent-local SatelliteAgentState beliefs
             │
             ▼
ProtocolContext (frozen views + copied trajectories)
             │
             ▼
ManeuverProposal
             │
             ▼
ManeuverValidator ── rejected ──► trace + unresolved metric
             │ accepted
             ▼
ManeuverExecutor updates WorldState and fuel exactly once
             │
             ▼
Risk reassessment + secondary-risk scan
             │
             ▼
MetricsSummary + SimulationTrace ──► run artifacts
                                      │
                                      ▼
                         read-only local viewer
```

## State ownership

- `WorldState.trajectories` is current physical truth. Only execution updates it.
- `WorldState.original_trajectories` is a deep copy retained for comparison.
- `SatelliteAgentState` owns beliefs, known risks, neighbors, fuel, commitments, and maneuver history.
- `ProtocolContext` provides frozen agent views and copied trajectory values. Centralized and local protocols receive different visibility.
- `ManeuverProposal` owns proposal, validation, and execution lifecycle fields.
- `ManeuverValidator` independently checks deadlines, bounds, resources, target improvement, duplicates, and configured secondary-risk policy.
- `SimulationTrace` records ordered transitions; metrics evaluate the resulting run rather than control it.

These boundaries make information access and state mutation explicit. They also allow the same scenario to be evaluated under different protocols without one protocol silently rewriting initial truth.

## Execution lifecycle

The current closed-loop runner constructs initial linear trajectories, detects risk at simulation step zero, transmits alerts, waits through configured latency, asks the selected protocol for proposals, validates each proposal, executes valid ones, and reassesses over the configured horizon. This is a deliberately small benchmark lifecycle, not a continuously propagating orbital operations loop.

The older `run_scenario` open-loop API remains for backward compatibility. The external CLI uses `run_closed_loop_scenario` and the artifact layer.

The viewer is downstream of standard artifacts. `src.viewer.model` validates and normalizes artifact schemas, builds event/reference indexes, and derives presentation state. `src.viewer.server` serves only those immutable data structures and packaged frontend assets over loopback HTTP. No viewer module imports or invokes simulation execution.

## Public interfaces

External users should depend on the `themis` CLI, TOML schema, and documented `themis.*` Python modules. Protocol authors import `CoordinationProtocol`, `ProtocolContext`, `ProtocolDecision`, and `check_protocol` from `themis.protocols`; implementations may be distributed separately through the `themis.protocols` Python entry-point group. `themis.artifacts` is the viewer-independent, read-only run loader. Other `src.*` modules remain internal and may evolve before version 1.0.

The package follows semantic versioning. During the 0.x series, documented CLI, configuration, and protocol-interface breaking changes require a minor-version increment and migration notes.
