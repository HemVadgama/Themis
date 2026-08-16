"""Replicate-aware descriptive analysis for completed parameter sweeps."""

import csv
import json
import math
from pathlib import Path
from statistics import mean, stdev


class AnalysisError(ValueError):
    """A sweep cannot be analyzed as requested."""


_NON_METRICS = {
    "seed",
    "runtime_seconds",
    "status",
    "error",
    "run_id",
    "experiment",
    "scenario",
    "protocol",
    "benchmark",
    "outcome",
}

# Two-sided 95% Student-t critical values for 1..30 degrees of freedom.
_T95 = (
    None,
    12.706,
    4.303,
    3.182,
    2.776,
    2.571,
    2.447,
    2.365,
    2.306,
    2.262,
    2.228,
    2.201,
    2.179,
    2.160,
    2.145,
    2.131,
    2.120,
    2.110,
    2.101,
    2.093,
    2.086,
    2.080,
    2.074,
    2.069,
    2.064,
    2.060,
    2.056,
    2.052,
    2.048,
    2.045,
    2.042,
)


def _t_critical_95(sample_size):
    degrees = sample_size - 1
    return _T95[degrees] if degrees <= 30 else 1.96


def _load_records(path):
    source = Path(path).expanduser().resolve()
    if source.is_dir():
        source = source / "aggregate.json"
    if not source.is_file():
        raise AnalysisError(f"Sweep aggregate not found: {source}")
    try:
        records = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise AnalysisError(f"Invalid JSON in {source}: {error.msg}.") from error
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise AnalysisError(f"Invalid sweep aggregate {source}: expected an array of objects.")
    successful = [record for record in records if record.get("status") != "failed"]
    if not successful:
        raise AnalysisError("Sweep has no successful runs to analyze.")
    return source, successful, len(records) - len(successful)


def _default_group_fields(records):
    fields = sorted({key for record in records for key in record if "." in key})
    return [field for field in fields if field != "experiment.seed"]


def _default_metrics(records, group_fields):
    fields = set.intersection(*(set(record) for record in records))
    return sorted(
        field
        for field in fields
        if field not in _NON_METRICS
        and field not in group_fields
        and "." not in field
        and all(
            isinstance(record[field], (int, float)) and not isinstance(record[field], bool)
            for record in records
        )
    )


def analyze_sweep(path, *, group_by=None, metrics=None, confidence=0.95, output_directory=None):
    """Summarize repeated seeds with means, sample SDs, SEs, and t intervals.

    Failed runs and observational ``runtime_seconds`` are excluded. The confidence
    interval is intentionally limited to a two-sided 95% Student-t interval: it is
    transparent, dependency-free, and appropriate only when seeds are independent
    replicates of the same condition.
    """
    if confidence != 0.95:
        raise AnalysisError("Only confidence=0.95 is currently supported.")
    source, records, failed_run_count = _load_records(path)
    group_fields = list(group_by) if group_by is not None else _default_group_fields(records)
    metric_fields = list(metrics) if metrics is not None else _default_metrics(records, group_fields)
    available = set().union(*(set(record) for record in records))
    unknown = [field for field in (*group_fields, *metric_fields) if field not in available]
    if unknown:
        raise AnalysisError(f"Unknown aggregate field(s): {', '.join(unknown)}.")
    if not metric_fields:
        raise AnalysisError("No numeric metric fields are available to analyze.")

    groups = {}
    for record in records:
        key = tuple(record.get(field) for field in group_fields)
        groups.setdefault(key, []).append(record)

    rows = []
    for group_key in sorted(groups, key=lambda value: tuple(str(item) for item in value)):
        replicas = groups[group_key]
        group = dict(zip(group_fields, group_key))
        replica_seeds = [record.get("seed", record.get("experiment.seed")) for record in replicas]
        if any(seed is None for seed in replica_seeds):
            raise AnalysisError(f"Condition {group!r} has a run without a seed.")
        seeds = set(replica_seeds)
        if len(seeds) != len(replica_seeds):
            raise AnalysisError(
                f"Condition {group!r} contains duplicate seed rows; each seed must identify one independent run."
            )
        for metric in metric_fields:
            values = [float(record[metric]) for record in replicas if isinstance(record.get(metric), (int, float))]
            n = len(values)
            average = mean(values)
            sample_sd = stdev(values) if n >= 2 else None
            standard_error = sample_sd / math.sqrt(n) if sample_sd is not None else None
            margin = _t_critical_95(n) * standard_error if n >= 2 else None
            rows.append(
                {
                    **group,
                    "metric": metric,
                    "n": n,
                    "seed_count": len(seeds),
                    "mean": average,
                    "sample_sd": sample_sd,
                    "standard_error": standard_error,
                    "ci95_low": average - margin if margin is not None else None,
                    "ci95_high": average + margin if margin is not None else None,
                }
            )

    destination = Path(output_directory).expanduser().resolve() if output_directory else source.parent / "analysis"
    destination.mkdir(parents=True, exist_ok=True)
    payload = {
        "analysis_schema_version": 1,
        "source": str(source),
        "run_counts": {"successful": len(records), "failed_excluded": failed_run_count},
        "method": {
            "name": "two-sided Student-t confidence interval",
            "confidence": confidence,
            "replicate_unit": "seed",
            "assumptions": [
                "Runs within a group differ only in independent replicate seeds.",
                "The sample mean is an appropriate estimand for the selected metric.",
                "For small n, the sampling distribution is approximately normal.",
            ],
            "excluded": ["failed runs", "runtime_seconds"],
        },
        "group_by": group_fields,
        "metrics": metric_fields,
        "rows": rows,
    }
    (destination / "analysis.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    columns = [*group_fields, "metric", "n", "seed_count", "mean", "sample_sd", "standard_error", "ci95_low", "ci95_high"]
    with (destination / "analysis.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return destination, payload
