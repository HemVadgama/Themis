"""Sequential, failure-tolerant parameter sweeps."""

import csv
from itertools import product
import json
from pathlib import Path
import tomllib

from src.artifacts import deterministic_run_id, write_run_artifacts
from src.configuration import ConfigurationError, load_experiment_config
from src.simulation.dispatch import run_experiment


def load_sweep(path):
    sweep_path = Path(path).expanduser().resolve()
    if not sweep_path.is_file():
        raise ConfigurationError(f"Sweep file not found: {sweep_path}")
    try:
        with sweep_path.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise ConfigurationError(f"Malformed TOML in {sweep_path}: {error}") from error
    if set(data) != {"sweep"} or not isinstance(data["sweep"], dict):
        raise ConfigurationError("Invalid sweep: expected one [sweep] table.")
    sweep = data["sweep"]
    if set(sweep) != {"base_config", "grid"}:
        raise ConfigurationError("Invalid [sweep]: require base_config and grid only.")
    if not isinstance(sweep["base_config"], str) or not isinstance(sweep["grid"], dict) or not sweep["grid"]:
        raise ConfigurationError("Invalid [sweep]: base_config must be a path and grid must be a non-empty table.")
    for key, values in sweep["grid"].items():
        if not isinstance(values, list) or not values:
            raise ConfigurationError(f"Invalid sweep.grid.{key}: expected a non-empty array.")
    base_path = (sweep_path.parent / sweep["base_config"]).resolve()
    return base_path, sweep["grid"]


def run_sweep(path, progress=print):
    base_path, grid = load_sweep(path)
    keys = sorted(grid)
    combinations = list(product(*(grid[key] for key in keys)))
    first_config = load_experiment_config(base_path)
    sweep_directory = first_config.output_directory / (Path(path).stem + "-sweep")
    sweep_directory.mkdir(parents=True, exist_ok=True)
    records = []
    progress(f"Sweep: {len(combinations)} run(s)")
    for index, values in enumerate(combinations, start=1):
        overrides = dict(zip(keys, values))
        try:
            configuration = load_experiment_config(base_path, overrides=overrides)
            run_id = deterministic_run_id(configuration)
            summary_path = configuration.output_directory / run_id / "summary.json"
            if summary_path.is_file():
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                status = "resumed"
            else:
                result = run_experiment(configuration)
                _, summary = write_run_artifacts(configuration, result)
                status = "completed"
            record = {"status": status, **overrides, **summary, **summary["metrics"]}
            record.pop("metrics", None)
            progress(f"[{index}/{len(combinations)}] {status}: {summary['run_id']}")
        except (ConfigurationError, OSError, ValueError) as error:
            record = {"status": "failed", **overrides, "error": str(error)}
            progress(f"[{index}/{len(combinations)}] failed: {error}")
        records.append(record)
    columns = sorted({key for record in records for key in record})
    with (sweep_directory / "aggregate.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)
    (sweep_directory / "aggregate.json").write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sweep_directory, records
