# Example experiments

These examples exercise the real closed-loop pipeline. Units are benchmark units,
not flight-dynamics quantities.

| Example | Command | Expected qualitative result |
|---|---|---|
| Basic conjunction | `themis run examples/basic.toml` | Centralized coordination proposes, validates, executes, and reassesses one maneuver; the conjunction resolves. |
| Protocol comparison | `themis compare examples/protocol-comparison.toml --protocol centralized --protocol greedy` | Both protocols see the same initial truth; their selected maneuvering agent and resource burden can differ. |
| Network degradation | `themis run examples/network-degradation.toml` | Greedy coordination depends on delivered alerts; seeded loss or latency can leave the risk unresolved. |
| Safety rejection | `themis run examples/safety-rejection.toml` | A proposal is rejected with `INSUFFICIENT_FUEL`; physical truth is not mutated. |
| Parameter sweep | `themis sweep examples/network-sweep.toml` | Runs 36 protocol/network/seed combinations and writes aggregate CSV and JSON; follow with `themis analyze results/network-sweep-sweep`. |
| Viewer demo | `themis run examples/viewer-demo.toml` | One risk alert is delivered and one is dropped; local knowledge, a valid action, execution, and resolution are all visible in the viewer. |
| Viewer blackout comparison | `themis run examples/viewer-demo-blackout.toml` | Both alerts are dropped, so greedy coordination cannot act; compare it with `viewer-demo` to inspect the divergence. |

Every individual run writes `config.toml`, `summary.json`, `metrics.csv`,
`events.jsonl`, and `metadata.json` under `results/<run-id>/`. Comparison and
sweep commands additionally write aggregate files in a named subdirectory.
