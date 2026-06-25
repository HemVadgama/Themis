# Protocol Arena

Themis is evolving from an orbital propagation project into a distributed autonomy benchmark platform. Space traffic management is the first domain: satellites are propagated, conjunctions are detected, and coordination protocols decide how agents should respond under communication constraints.

This phase is intentionally small. It creates the runtime, agent, network, protocol, and metrics seams needed for future auction protocols, gossip protocols, richer fault injection, replay, observability, reinforcement learning, and LLM agents.

## Simulation Core

The simulation layer provides deterministic seeded runs, a simulation clock, event scheduling, scenario configuration, world state, and an experiment runner.

Run the first CLI experiment from the project root:

```bash
python -m src.simulation.runner --scenario simple_10 --protocol greedy --seed 42
```

Optionally write structured JSON output:

```bash
python -m src.simulation.runner --scenario simple_10 --protocol centralized --seed 42 --output-json results/protocol_run.json
```

## Agent Layer

Satellite agents track:

- agent ID
- satellite name
- current position reference
- fuel budget
- mission priority
- known neighbors
- risk state
- planned action

The first agents are deterministic and rule-based. They do not use LLMs or reinforcement learning.

## Network Layer

The network simulator supports:

- message latency
- packet loss
- bandwidth/message limits per agent per simulation step
- queued delivery
- deterministic behavior under a random seed

Message types include state advertisements, risk alerts, maneuver intents, coordination requests, and coordination responses.

## Protocol Layer

Two starter protocols are included:

- `centralized`: uses global conjunction information and assigns one satellite in each risky pair to maneuver.
- `greedy`: uses local risk state and known risk alerts; each risky agent independently plans a maneuver.

Auction and gossip protocols are intentionally left as TODOs until the foundation has replay, richer fault injection, and stronger observability.

## Metrics

The runner reports:

- conjunctions detected
- coordination attempts
- planned maneuvers
- messages sent
- messages delivered
- messages dropped
- estimated fuel used
- unresolved high-risk conjunctions
- runtime seconds

## Not Included Yet

This phase does not include a dashboard, LLM agents, reinforcement learning, maneuver physics, collision probability modeling, or a generic multi-domain framework. The goal is a minimal, testable protocol arena that can grow from the space traffic management domain.
