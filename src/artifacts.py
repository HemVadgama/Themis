"""Creation of inspectable run directories and machine-readable artifacts."""

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from src.version import __version__


ARTIFACT_SCHEMA_VERSION = 3


def validate_artifact_payloads(metadata, summary, events):
    """Validate the dependency-free core represented by the packaged schemas."""
    version = metadata.get("artifact_schema_version")
    if version not in {2, 3}:
        raise ValueError(f"Unsupported emitted artifact schema version {version!r}.")
    summary_required = {"run_id", "experiment", "benchmark", "scenario", "protocol", "seed", "outcome", "metrics"}
    missing = summary_required - set(summary)
    if missing:
        raise ValueError(f"Emitted summary is missing: {', '.join(sorted(missing))}.")
    if version == 3 and summary["benchmark"] != "spacecraft-campaign-v1":
        raise ValueError("Artifact schema v3 is reserved for spacecraft-campaign-v1.")
    if summary["outcome"] not in {"resolved", "unresolved", "no-conjunctions"}:
        raise ValueError(f"Invalid emitted outcome {summary['outcome']!r}.")
    for index, event in enumerate(events):
        required = {"time", "sequence", "event_type", "category", "payload", "entity_ids", "references"}
        if required - set(event):
            raise ValueError(f"Emitted event {index} does not satisfy event-v{version}.schema.json.")
        if event["sequence"] != index or not isinstance(event["time"], int) or event["time"] < 0:
            raise ValueError(f"Emitted event {index} has invalid deterministic identity.")
        if len(event["entity_ids"]) != len(set(event["entity_ids"])):
            raise ValueError(f"Emitted event {index} has duplicate entity_ids.")
        if not all(isinstance(key, str) and isinstance(value, str) for key, value in event["references"].items()):
            raise ValueError(f"Emitted event {index} has non-string causal references.")
    return True


def deterministic_run_id(configuration):
    identity = configuration.resolved_dict()
    # Artifact placement is not part of the scientific experiment identity.
    identity.pop("output", None)
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    fingerprint = hashlib.sha256(encoded).hexdigest()[:10]
    safe_name = "".join(character if character.isalnum() or character in "-_" else "-" for character in configuration.name).strip("-")
    return f"{safe_name}-{configuration.protocol}-s{configuration.seed}-{fingerprint}"


def _toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, list) and not any(isinstance(item, dict) for item in value):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"Cannot encode TOML value {value!r}")


def _toml_lines(table, prefix=""):
    lines = []
    scalar_items = [(key, value) for key, value in table.items() if value is not None and not isinstance(value, dict) and not (isinstance(value, list) and value and isinstance(value[0], dict))]
    child_tables = [(key, value) for key, value in table.items() if isinstance(value, dict)]
    array_tables = [(key, value) for key, value in table.items() if isinstance(value, list) and value and isinstance(value[0], dict)]
    if prefix:
        lines.append(f"[{prefix}]")
    lines.extend(f"{key} = {_toml_value(value)}" for key, value in scalar_items)
    for key, value in child_tables:
        if lines:
            lines.append("")
        lines.extend(_toml_lines(value, f"{prefix}.{key}" if prefix else key))
    for key, values in array_tables:
        for value in values:
            if lines:
                lines.append("")
            table_name = f"{prefix}.{key}" if prefix else key
            lines.append(f"[[{table_name}]]")
            lines.extend(f"{item_key} = {_toml_value(item_value)}" for item_key, item_value in value.items() if item_value is not None)
    return lines


def dumps_toml(data):
    return "\n".join(_toml_lines(data)).rstrip() + "\n"


def _git_commit(source_path):
    start = source_path.parent if source_path else Path.cwd()
    repository = next((candidate for candidate in (start, *start.parents) if (candidate / ".git").exists()), None)
    if repository is None:
        return None
    try:
        return subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def write_run_artifacts(configuration, result):
    run_id = deterministic_run_id(configuration)
    run_directory = configuration.output_directory / run_id
    run_directory.mkdir(parents=True, exist_ok=True)
    result["run_id"] = run_id
    result["trace"]["run_id"] = run_id

    resolved = configuration.resolved_dict()
    (run_directory / "config.toml").write_text(dumps_toml(resolved), encoding="utf-8")
    risk_count = result["metrics"].get("risks_created", result["metrics"]["original_conjunctions"])
    unresolved_count = result["metrics"].get("risks_unresolved", result["metrics"]["unresolved_conjunctions"])
    if risk_count == 0:
        outcome = "no-conjunctions"
    elif unresolved_count == 0:
        outcome = "resolved"
    else:
        outcome = "unresolved"
    summary = {
        "run_id": run_id,
        "experiment": configuration.name,
        "benchmark": configuration.benchmark,
        "scenario": result["scenario"],
        "protocol": result["protocol"],
        "seed": result["seed"],
        "outcome": outcome,
        "metrics": result["metrics"],
    }
    artifact_version = 3 if configuration.benchmark == "spacecraft-campaign-v1" else 2
    metadata = {
        "artifact_schema_version": artifact_version,
        "run_id": run_id,
        "benchmark": configuration.benchmark,
        "themis_version": __version__,
        "git_commit": _git_commit(configuration.source_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "determinism_note": "Model-derived values are deterministic for the same config, seed, and version; timestamps and runtime are observational.",
        "user_metadata": configuration.metadata,
    }
    validate_artifact_payloads(metadata, summary, result["trace"]["events"])
    (run_directory / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (run_directory / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        flat_metrics = {key: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value for key, value in result["metrics"].items()}
        writer = csv.DictWriter(handle, fieldnames=["run_id", "experiment", "benchmark", "scenario", "protocol", "seed", *flat_metrics])
        writer.writeheader()
        writer.writerow({"run_id": run_id, "experiment": configuration.name, "benchmark": configuration.benchmark, "scenario": result["scenario"], "protocol": result["protocol"], "seed": result["seed"], **flat_metrics})
    with (run_directory / "events.jsonl").open("w", encoding="utf-8") as handle:
        for event in result["trace"]["events"]:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    (run_directory / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return run_directory, summary
