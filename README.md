# Themis

Themis is a deterministic experimental testbed for comparing autonomous and distributed coordination strategies under configurable communication, execution, resource, and safety constraints. Its first benchmark domain is simplified space traffic coordination.

It helps researchers ask questions such as: how does a local protocol behave when risk alerts are late or lost, how does it compare with a centralized policy on the same initial state, and which proposed actions an independent safety layer rejects?

Themis is **not** an operational conjunction-assessment system, orbit-determination tool, maneuver planner, spacecraft controller, or source of flight-safety advice. The closed-loop examples use linear benchmark trajectories and threshold-based risk. See [assumptions and limitations](docs/assumptions-and-limitations.md).

## Five-minute quick start

Python 3.11 or 3.12 is supported.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install ".[dev]"
themis run examples/basic.toml
```

A successful run prints a concise safety, communication, and maneuver summary:

```text
Run: basic-conjunction-centralized-s42-9cd2d4016a
Scenario / protocol / seed: basic-conjunction / centralized / 42
Outcome: resolved
Safety: 1 initial, 1 resolved, 0 unresolved, 0 validator rejection(s)
Communication: 2 sent, 2 delivered, 0 dropped
Maneuvers: 1 executed, 80.0 km/step delta-v proxy
Artifacts: .../results/basic-conjunction-centralized-s42-9cd2d4016a
```

That directory contains the resolved `config.toml`, `summary.json`, one-row `metrics.csv`, ordered `events.jsonl`, and version/provenance `metadata.json`. The run ID is derived from the resolved configuration.

## What to run next

Edit a TOML file to change the seed, protocol, latency, packet loss, maneuver bounds, thresholds, or initial linear states—no source edit is required.

```bash
# Compare protocols on identical initial conditions
themis compare examples/protocol-comparison.toml \
  --protocol centralized --protocol greedy

# Run a protocol × loss × latency × seed grid
themis sweep examples/network-sweep.toml

# Validate without running, or inspect an event stream
themis validate examples/basic.toml
themis replay results/<run-id>
```

See every curated example and its expected qualitative outcome in [examples/README.md](examples/README.md).

## Architecture

```text
Scenario / linear initial truth
              ↓
       physical WorldState
              ↓
    conjunction detection
              ↓
 risk alerts through NetworkSimulator
              ↓
 restricted ProtocolContext (agent views)
              ↓
       maneuver proposal
              ↓
 independent ManeuverValidator
              ↓
        ManeuverExecutor
              ↓
 world trajectory update + reassessment
              ↓
       metrics + event trace
```

Physical truth, agent-local beliefs, protocol decisions, safety validation, and execution have separate owners. Protocols receive copied trajectories and frozen agent views; they propose actions but cannot execute them. The detailed rationale and state ownership are in [architecture.md](docs/architecture.md).

## Create and reproduce an experiment

Copy [examples/basic.toml](examples/basic.toml), give the experiment a name, and change its tables. The configuration is strictly validated before the simulation starts. Relative output paths are resolved relative to the configuration file. The saved resolved config can itself be passed back to `themis run`.

Identical resolved configuration, seed, and Themis version produce identical model decisions and outcomes. Wall-clock runtime and artifact creation timestamp are observational and therefore excluded from that guarantee. Commit and package version are recorded when available.

The complete schema is in [configuration.md](docs/configuration.md), metric definitions are in [metrics.md](docs/metrics.md), and batch behavior is in [experiments.md](docs/experiments.md).

## Add a protocol

Implement the narrow `CoordinationProtocol` contract, operate only on `ProtocolContext`, and register the class explicitly in `src/protocols/registry.py`. A minimal implementation lives in `src/protocols/example.py`; the lifecycle, determinism rules, and test pattern are documented in [protocols.md](docs/protocols.md).

## Development and deeper documentation

- [Getting started](docs/getting-started.md)
- [Configuration reference](docs/configuration.md)
- [Experiment and sweep guide](docs/experiments.md)
- [Protocol authoring](docs/protocols.md)
- [Metrics reference](docs/metrics.md)
- [Assumptions and limitations](docs/assumptions-and-limitations.md)
- [Contributor guide](CONTRIBUTING.md)
- [Roadmap](docs/roadmap.md)

Run `themis --help`, `themis run --help`, or the full test suite with `python -m pytest`.

## License

Themis is available under the [Apache License 2.0](LICENSE).
