# Experiments and batch runs

For a complete multi-cycle protocol study, use `studies/auction-network-faults/`. Its smoke and publication grids are ordinary resumable sweeps; raw run rows stay paired by seed and analysis remains downstream of immutable artifacts.

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

## Replicate-aware analysis

Include multiple `experiment.seed` values when estimating variability. After a sweep, run:

```bash
themis analyze results/network-sweep-sweep
```

By default, dotted sweep parameters other than `experiment.seed` define experimental conditions. Themis writes long-form `analysis.csv` and self-describing `analysis.json` with sample size, seed count, mean, sample standard deviation, standard error, and a two-sided 95% Student-t interval for every numeric metric. Failed runs and observational runtime are excluded. Select fields explicitly with repeated `--group-by` and `--metric` options.

The interval assumes seeds are independent replicates of the same condition and that a mean/t interval is appropriate. It is descriptive evidence, not an automatic hypothesis test or proof of external validity. With one replicate, dispersion and interval fields are empty. See [methodology](methodology.md) before reporting results.

## Artifact contract

- `config.toml`: complete resolved input and the primary reproduction record.
- `summary.json`: identifiers, final outcome, and aggregate metrics.
- `metrics.csv`: one row suitable for dataframe ingestion.
- `events.jsonl`: ordered lifecycle events with time, sequence, type, and payload.
- `metadata.json`: Themis version, git commit where available, creation timestamp, determinism note, and user metadata.

Core JSON Schemas ship in `themis/schemas/` and can be located programmatically with `themis.artifacts.schema_path()`. Readers must tolerate unknown payload and metric fields within the same artifact schema generation. Use `themis.artifacts.load_run()` to stream events without importing the viewer.

Output directories are user-selected. Themis creates files below that directory but does not delete old data or invoke a shell.
