# Metrics

Metrics report quantities defined by the `spacecraft-coordination-v1` simulation model.

## Directly measured simulation counts

- Safety: `original_conjunctions`, `resolved_conjunctions`, `unresolved_conjunctions`, `worsened_conjunctions`, `secondary_conjunctions_created`, and `safety_validation_failures`.
- Maneuver lifecycle: `maneuvers_proposed`, `maneuvers_rejected`, `maneuvers_executed`, and `maneuvers_failed`.
- Communication: `messages_sent`, `messages_delivered`, `messages_dropped`, and `messages_delayed_beyond_usefulness`.
- Coordination: `coordination_attempts`, `successful_agreements`, `timeouts`, duplicate proposals, conflicts, and fallback activations.

## Derived simulation metrics

- Minimum pre/post separation is the minimum Euclidean distance over the configured discrete reassessment horizon.
- Average communication latency is delivered step minus sent step for delivered messages only; dropped messages are excluded.
- Detection-to-decision and decision-to-execution values are discrete step counts.
- Per-agent burden and remaining fuel derive from accepted/executed state changes.
- Delta-v per resolved conjunction divides total simulated delta-v by resolved conjunction count and is absent when none resolve.

## Explicit proxies

`total_delta_v_used_km_per_step` uses velocity change per simulation step, not physical km/s. `estimated_fuel_used` currently equals proposal delta-v magnitude, and `mission_disruption_cost` is `0.1 × magnitude`. These are comparison proxies, not propellant mass, mission cost, or flight-qualified performance.

`runtime_seconds` is wall-clock performance and nondeterministic. All other metrics are intended to be deterministic for a fixed resolved config, seed, and version.
