# Configuration reference

Experiment files are UTF-8 TOML. Unknown sections and fields fail validation; numeric types and bounds are checked without silent string coercion. Run `themis validate path/to/config.toml` to see the fully resolved configuration.

## Tables

| Table | Fields | Meaning |
|---|---|---|
| `experiment` | `name` (required), `seed`, `metadata` | Identity, controlled randomness, optional user labels. Seed is a non-negative integer. |
| `scenario` | `preset`, `name`, `agent_count`, `duration_steps`, `decision_deadline_steps`, `risk_reassessment_horizon_steps`, `initial_states`, `mission_priorities`, `fuel_budgets` | Built-in initial condition and explicit overrides. Initial states are 3-component position and velocity vectors. |
| `protocol` | `name` | `centralized`, `greedy`, or `example-lowest-id`. |
| `network` | `latency_steps`, `packet_loss_rate`, `bandwidth_limit_per_agent` | Fixed step latency, seeded independent loss in `[0,1]`, and per-sender/per-step message cap. |
| `safety` | `conjunction_threshold_km`, `maneuver_threshold_km`, `secondary_conjunction_threshold_km`, `allow_secondary_risk` | Distance thresholds and whether a validator may accept a proposal with a detected secondary risk. |
| `maneuver` | `min_delta_v_km_per_step`, `max_delta_v_km_per_step`, `default_fuel_budget` | Bounds and benchmark resource budget. Minimum may not exceed maximum. |
| `execution` | `failure_rate`, `magnitude_error_fraction` | Seeded failure probability and deterministic positive magnitude bias. |
| `output` | `directory` | Run root. A relative path is relative to the config file, not the shell's working directory. |

Defaults come from the selected preset. Built-in presets are `closed_loop_resolved`, `closed_loop_insufficient_fuel`, `closed_loop_late_response`, `closed_loop_packet_loss`, `closed_loop_secondary`, `closed_loop_protocol_difference`, and `closed_loop_execution_error`.

The CLI intentionally does not import protocol classes or execute code named in a configuration file. Protocol registration is an explicit source-code operation.

## Inline initial state

Each `[[scenario.initial_states]]` entry must contain exactly `agent_id`, `position_km`, and `velocity_km_per_step`; IDs must be unique and the count must match `scenario.agent_count`. The resolved config produced by every run is a complete working example.

Normal mistakes return a short message and exit status 2. Add global `--debug` before the command when a developer traceback is useful.
