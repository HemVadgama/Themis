# Experiments and batch runs

Run one configuration with `themis run CONFIG`. The run ID combines the experiment name, protocol, seed, and a SHA-256 prefix of the resolved configuration. Repeating an identical experiment therefore addresses the same run directory.

`themis compare CONFIG --protocol centralized --protocol greedy` runs identical initial conditions under each listed protocol and writes `comparison.csv` and `comparison.json` alongside the individual run directories.

## Sweeps

A sweep references a base experiment and defines a Cartesian grid:

```toml
[sweep]
base_config = "network-degradation.toml"

[sweep.grid]
"protocol.name" = ["centralized", "greedy"]
"network.packet_loss_rate" = [0.0, 0.5, 1.0]
"network.latency_steps" = [0, 1, 3]
"experiment.seed" = [1, 2]
```

Run `themis sweep SWEEP.toml`. Execution is intentionally sequential and easy to inspect. Every cell has normal run artifacts. The sweep writes `aggregate.csv` and `aggregate.json`; a failed cell is recorded and later cells still run. Existing run IDs with a `summary.json` are treated as completed, making reruns resumable.

Resumability assumes an existing summary is complete and was not manually edited. Delete or move that individual run directory to force recomputation.

## Artifact contract

- `config.toml`: complete resolved input and the primary reproduction record.
- `summary.json`: identifiers, final outcome, and aggregate metrics.
- `metrics.csv`: one row suitable for dataframe ingestion.
- `events.jsonl`: ordered lifecycle events with time, sequence, type, and payload.
- `metadata.json`: Themis version, git commit where available, creation timestamp, determinism note, and user metadata.

Output directories are user-selected. Themis creates files below that directory but does not delete old data or invoke a shell.
