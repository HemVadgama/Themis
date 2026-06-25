# Themis

Themis is a Python simulation and benchmarking platform for space traffic management and distributed autonomy research.

The project starts with the orbital domain: loading real satellite TLE data, propagating satellite positions, detecting conjunctions, and testing coordination protocols under constrained communication. The long-term goal is to provide a reusable research environment for evaluating how autonomous systems coordinate when safety, latency, bandwidth, and incomplete information matter.

## Project Goals

Themis is designed to support experiments around:

- satellite orbit propagation using real-world TLE data
- conjunction detection across many satellites and timestamps
- collision-risk and close-approach analysis
- deterministic simulation scenarios
- satellite agent behavior and coordination policies
- constrained communication networks with latency, packet loss, and bandwidth limits
- protocol benchmarking for centralized and decentralized autonomy

Space traffic management is the first domain. The architecture is being kept modular enough to support future domains without becoming a generic framework before the satellite use case is solid.

## Current Capabilities

### Orbital Propagation

The propagation layer can:

- load satellite TLE data
- parse satellites into Skyfield propagatable objects
- propagate positions using SGP4
- generate ECI position records with `satellite`, `time`, `x_km`, `y_km`, and `z_km`
- build position tables across many satellites and timestamps

### Conjunction Detection

The detection layer can:

- calculate Euclidean distance between two position records
- detect satellite pairs within a configurable distance threshold
- scan position tables across multiple timestamps
- report conjunction events sorted by time and distance
- compute closest observed approaches for each satellite pair
- export structured records to CSV

### Protocol Arena Foundation

The simulation foundation can:

- run deterministic seeded scenarios
- manage a simulation clock and event ordering
- create satellite agents with fuel budget, mission priority, risk state, known neighbors, and planned action
- simulate communication latency, packet loss, bandwidth limits, and queued delivery
- compare centralized and greedy coordination protocols
- report metrics for safety, coordination, communication, fuel use, and runtime

The protocol arena is intentionally minimal. It is a foundation for future auction, gossip, replay, observability, reinforcement learning, and LLM-agent experiments.

## Repository Structure

```text
src/
  propagation/     TLE loading and satellite propagation
  detection/       Distance calculations and conjunction detection
  simulation/      Deterministic runtime, scenarios, world state, CLI runner
  agents/          Satellite agent state and rule-based behavior
  network/         Message types and constrained network simulator
  protocols/       Coordination protocol interfaces and implementations
  metrics/         Safety, efficiency, and run summary metrics
  utils/           Shared utilities such as CSV export

experiments/       Research scripts and experiment entry points
docs/              Architecture notes and protocol arena documentation
tests/             Pytest test suite
results/           Generated experiment outputs
data/              Local TLE data cache
```

## Installation

Create and activate a virtual environment, then install the dependencies used by the project.

```bash
python -m venv .venv
source .venv/bin/activate
pip install skyfield pandas numpy pytest
```

The current repository does not yet include a pinned dependency file. Until one is added, the commands above describe the expected local development environment.

## Usage

Run the conjunction detection demo:

```bash
.venv/bin/python -m src.detection.demo_conjunctions
```

Run the first protocol arena experiment:

```bash
.venv/bin/python -m src.simulation.runner --scenario simple_10 --protocol greedy --seed 42
```

Run the same experiment with centralized coordination:

```bash
.venv/bin/python -m src.simulation.runner --scenario simple_10 --protocol centralized --seed 42
```

Write protocol results to JSON:

```bash
.venv/bin/python -m src.simulation.runner --scenario simple_10 --protocol greedy --seed 42 --output-json results/protocol_run.json
```

Example protocol summary:

```text
Protocol: greedy
Agents: 10
Seed: 42
Conjunctions detected: 54
Coordination attempts: 54
Maneuvers planned: 60
Messages sent: 108
Messages delivered: 94
Messages dropped: 14
Estimated fuel used: 60.0
Unresolved high-risk conjunctions: 0
Runtime seconds: 0.000502
```

## Testing

Run the full test suite from the project root:

```bash
.venv/bin/python -m pytest
```

The tests cover:

- distance calculation and validation
- conjunction detection behavior
- CSV export
- simulation event ordering
- deterministic seeded runs
- network delivery, packet loss, and bandwidth limits
- centralized and greedy protocol decisions
- metrics summary output

## Architecture

The current architecture is organized as a pipeline plus a protocol arena:

```text
TLE Data
   |
   v
Propagation Engine
   |
   v
Position Tables
   |
   v
Conjunction Detection
   |
   v
Simulation World
   |
   +--> Satellite Agents
   +--> Network Simulator
   +--> Coordination Protocols
   |
   v
Metrics and Results
```

The orbital propagation and conjunction detection layers remain independent from the protocol arena. This keeps physical state generation separate from coordination logic and makes experiments easier to test.

## Metrics

Protocol arena runs currently report:

- conjunctions detected
- coordination attempts
- planned maneuvers
- messages sent
- messages delivered
- messages dropped
- estimated fuel used
- unresolved high-risk conjunctions
- runtime seconds

## Roadmap

### Completed

- TLE loading and satellite propagation
- position-table generation
- pairwise distance calculation
- conjunction event detection
- closest-approach summaries
- CSV export utility
- deterministic simulation core
- basic satellite agent model
- constrained network simulator
- centralized and greedy protocols
- metrics summary and CLI runner

### Near-Term Work

- connect protocol arena scenarios to real propagated position tables
- add richer risk scoring beyond distance thresholding
- add maneuver cost models and action constraints
- improve scenario configuration and experiment reproducibility
- add replayable simulation traces
- add benchmark comparisons between centralized and decentralized protocols

### Later Research Directions

- auction-based coordination
- gossip-based coordination
- fault-injection studies
- large-scale constellation experiments
- reinforcement learning policies
- LLM-assisted agents or operators
- visualization and dashboard tooling

## Current Limitations

Themis is still an active research codebase.

Current limitations include:

- conjunction risk is distance-threshold based, not probabilistic
- maneuver planning is represented as a planned action, not physical orbit modification
- protocol arena scenarios currently use deterministic synthetic positions
- communication models are simple latency/loss/bandwidth abstractions
- no dashboard or interactive visualization is included
- no reinforcement learning or LLM agents are included

Propagation accuracy depends on public TLE data quality and the standard SGP4 model.

## Documentation

Additional project notes:

- [Protocol Arena](docs/protocol_arena.md)
- [Architecture](docs/architecture.md)
- [Experiments](docs/experiments.md)
- [Roadmap](docs/roadmap.md)
- [Vision](docs/vision.md)

## Development Philosophy

Themis is being built as a research and engineering platform, not a polished application. The priority is deterministic, testable, modular simulation code that can grow into more advanced autonomy experiments without obscuring the orbital mechanics and safety assumptions underneath.
