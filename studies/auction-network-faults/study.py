"""Run and analyze the dependency-free auction/network-fault study."""

import argparse
import csv
import json
from pathlib import Path
import shutil
import sys
from itertools import product
from statistics import mean

ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.analysis import analyze_sweep
from src.artifacts import deterministic_run_id
from src.batch import load_sweep, run_sweep
from src.configuration import load_experiment_config
from src.simulation.dispatch import run_experiment
METRICS = [
    "resolution_probability",
    "risks_unresolved",
    "modeled_maneuver_cost",
    "messages_sent",
    "messages_dropped",
    "decision_deadline_misses",
    "auction_successes",
]


def _aggregate_path(profile):
    return ROOT / "results" / "runs" / f"{profile}-sweep" / "aggregate.json"


def _stable_rows(records):
    return sorted(
        [{key: value for key, value in record.items() if key not in {"status", "runtime_seconds", "error"}} for record in records],
        key=lambda record: record["run_id"],
    )


def run(profile):
    directory, records = run_sweep(ROOT / "configs" / f"{profile}.toml")
    failed = [record for record in records if record.get("status") == "failed"]
    if failed:
        raise RuntimeError(f"{len(failed)} study runs failed; inspect {directory / 'aggregate.json'}")
    return directory


def _write_svg(rows, destination):
    selected = [row for row in rows if row["metric"] == "resolution_probability"]
    width, height, margin = 760, 440, 55
    losses = sorted({float(row["network.packet_loss_rate"]) for row in selected})
    colors = {"centralized": "#2c7fb8", "greedy": "#f28e2b", "auction": "#4daf4a"}
    latency_styles = {0: "", 1: "6,4"}
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>']
    parts.append(f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="#333"/>')
    parts.append(f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="#333"/>')
    for value in (0, 0.25, 0.5, 0.75, 1.0):
        y = height - margin - value * (height - 2 * margin)
        parts.append(f'<line x1="{margin}" y1="{y:.1f}" x2="{width-margin}" y2="{y:.1f}" stroke="#ddd"/>')
        parts.append(f'<text x="8" y="{y+4:.1f}" font-size="12">{value:.2f}</text>')
    for index, loss in enumerate(losses):
        x = margin + (index / max(1, len(losses)-1)) * (width - 2 * margin)
        parts.append(f'<text x="{x-12:.1f}" y="{height-25}" font-size="12">{loss:g}</text>')
    for protocol in colors:
        for latency in sorted({int(row["network.latency_steps"]) for row in selected}):
            series = sorted((row for row in selected if row["protocol.name"] == protocol and int(row["network.latency_steps"]) == latency), key=lambda row: float(row["network.packet_loss_rate"]))
            points = []
            for row in series:
                x = margin + (losses.index(float(row["network.packet_loss_rate"])) / max(1, len(losses)-1)) * (width - 2 * margin)
                y = height - margin - float(row["mean"]) * (height - 2 * margin)
                points.append(f"{x:.1f},{y:.1f}")
            dash = latency_styles.get(latency, "2,3")
            parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{colors[protocol]}" stroke-width="2.5" stroke-dasharray="{dash}"/>')
    parts.extend([
        f'<text x="{width/2-75:.1f}" y="{height-5}" font-size="14">packet loss probability</text>',
        '<text x="15" y="25" font-size="14">mean modeled resolution fraction</text>',
        '<text x="500" y="25" font-size="12">solid: latency 0; dashed: latency 1</text>',
        '</svg>',
    ])
    destination.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _boundary_analysis(rows):
    resolution = [row for row in rows if row["metric"] == "resolution_probability"]
    boundaries = []
    for protocol in sorted({row["protocol.name"] for row in resolution}):
        for latency in sorted({row["network.latency_steps"] for row in resolution}):
            series = sorted((row for row in resolution if row["protocol.name"] == protocol and row["network.latency_steps"] == latency), key=lambda row: row["network.packet_loss_rate"])
            sampled = next((row for row in series if row["mean"] < 0.5), None)
            boundaries.append({"protocol": protocol, "latency_steps": latency, "sampled_failure_boundary": sampled["network.packet_loss_rate"] if sampled else None, "criterion": "first sampled loss with mean modeled resolution fraction < 0.5", "universal_boundary": False})
    rankings = []
    conditions = sorted({(row["network.packet_loss_rate"], row["network.latency_steps"]) for row in resolution})
    for loss, latency in conditions:
        values = {row["protocol.name"]: row["mean"] for row in resolution if row["network.packet_loss_rate"] == loss and row["network.latency_steps"] == latency}
        rankings.append({"packet_loss_rate": loss, "latency_steps": latency, "ranking": sorted(values, key=lambda name: (-values[name], name)), "means": values})
    return {"method": "deterministic scan of sampled smoke-study conditions", "boundaries": boundaries, "condition_rankings": rankings, "warning": "A sampled boundary or ranking is descriptive of this grid, not universal or statistically significant."}


def analyze(profile):
    aggregate = _aggregate_path(profile)
    destination = ROOT / "results" / profile
    destination.mkdir(parents=True, exist_ok=True)
    analysis_dir, payload = analyze_sweep(aggregate, metrics=METRICS, output_directory=destination / "analysis")
    shutil.copy2(aggregate, destination / "raw-runs.json")
    shutil.copy2(aggregate.with_suffix(".csv"), destination / "raw-runs.csv")
    # Keep checked-in tabular evidence byte-stable and friendly to Unix tooling.
    for csv_path in (analysis_dir / "analysis.csv", destination / "raw-runs.csv"):
        csv_path.write_text(csv_path.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    raw_records = json.loads(aggregate.read_text(encoding="utf-8"))
    (destination / "model-results.json").write_text(json.dumps(_stable_rows(raw_records), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    runtime_groups = {}
    for record in raw_records:
        key = (record["protocol.name"], record.get("scenario.agent_count", 4))
        runtime_groups.setdefault(key, []).append(float(record["runtime_seconds"]))
    runtime_rows = [
        {"protocol": key[0], "agent_count": key[1], "n": len(values), "mean_runtime_seconds": mean(values), "min_runtime_seconds": min(values), "max_runtime_seconds": max(values), "classification": "observational_host_performance"}
        for key, values in sorted(runtime_groups.items())
    ]
    with (destination / "runtime-scale.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(runtime_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(runtime_rows)
    rows = payload["rows"]
    with (destination / "summary-table.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    boundary = _boundary_analysis(rows)
    (destination / "boundary-analysis.json").write_text(json.dumps(boundary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_svg(rows, destination / "resolution-by-loss.svg")
    interpretation = [
        f"# Executed {profile} study results",
        "",
        f"The stored aggregate contains {payload['run_counts']['successful']} successful run-level observations and {payload['run_counts']['failed_excluded']} excluded failures.",
        "Seeds are paired protocol replicates. Each table row reports a mean and two-sided 95% Student-t interval under the assumptions recorded in `analysis/analysis.json`.",
        "",
        "`boundary-analysis.json` reports only the first sampled condition crossing a predeclared 0.5 modeled-resolution threshold and condition-specific rankings. It makes no significance or universal-boundary claim.",
        "Observed values are in `summary-table.csv`; causal explanations require inspection of the referenced run traces. The publication profile has not been executed merely because this analysis function exists.",
    ]
    if profile == "smoke":
        resolution = {
            (row["protocol.name"], float(row["network.packet_loss_rate"]), int(row["network.latency_steps"])): row
            for row in rows if row["metric"] == "resolution_probability"
        }
        interpretation.extend([
            "",
            "## Observed smoke outcomes",
            "",
            f"At zero loss/zero latency, centralized and greedy each resolved a mean {resolution[('centralized', 0.0, 0)]['mean']:.3f} and {resolution[('greedy', 0.0, 0)]['mean']:.3f} fraction of created modeled risks; auction resolved {resolution[('auction', 0.0, 0)]['mean']:.3f}.",
            f"At loss 0.3/latency 0, the observed means were greedy {resolution[('greedy', 0.3, 0)]['mean']:.3f}, centralized {resolution[('centralized', 0.3, 0)]['mean']:.3f}, and auction {resolution[('auction', 0.3, 0)]['mean']:.3f}. This is an observed ranking change between centralized and greedy, not a significance result.",
            f"With zero loss/latency 1, observed means fell to centralized {resolution[('centralized', 0.0, 1)]['mean']:.3f}, greedy {resolution[('greedy', 0.0, 1)]['mean']:.3f}, and auction {resolution[('auction', 0.0, 1)]['mean']:.3f}.",
            "The auction's sampled 0.5 failure boundary is already at loss 0 under both latency settings. Trace inspection shows concurrent auction reservations and multi-message deadlines as visible failure modes, but this mechanism is an explanation of these configured traces, not proof of a general auction property.",
            "Three replicates produce wide or degenerate intervals, including bounds outside the feasible [0,1] range because untransformed Student-t intervals were preregistered. The data are underdetermined for significance, fine crossover location, and universal protocol ranking.",
        ])
    (destination / "interpretation.md").write_text("\n".join(interpretation) + "\n", encoding="utf-8")
    return analysis_dir


def verify(profile):
    base, grid = load_sweep(ROOT / "configs" / f"{profile}.toml")
    keys = sorted(grid)
    fresh = []
    for values in product(*(grid[key] for key in keys)):
        overrides = dict(zip(keys, values))
        config = load_experiment_config(base, overrides=overrides)
        result = run_experiment(config)
        metrics = {key: value for key, value in result["metrics"].items() if key != "runtime_seconds"}
        risk_count = metrics.get("risks_created", metrics["original_conjunctions"])
        unresolved = metrics.get("risks_unresolved", metrics["unresolved_conjunctions"])
        outcome = "no-conjunctions" if risk_count == 0 else "resolved" if unresolved == 0 else "unresolved"
        fresh.append({"run_id": deterministic_run_id(config), **overrides, "experiment": config.name, "benchmark": config.benchmark, "scenario": result["scenario"], "protocol": result["protocol"], "seed": result["seed"], "outcome": outcome, **metrics})
    expected = json.loads((ROOT / "results" / profile / "model-results.json").read_text(encoding="utf-8"))
    actual = _stable_rows(fresh)
    if actual != expected:
        raise RuntimeError(f"{profile} deterministic model outputs differ from the checked-in results")
    print(f"Verified {len(actual)} deterministic {profile} model rows.")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "analyze", "verify", "all"))
    parser.add_argument("--profile", choices=("smoke", "publication"), default="smoke")
    args = parser.parse_args(argv)
    if args.action in {"run", "all"}:
        run(args.profile)
    if args.action in {"analyze", "all"}:
        analyze(args.profile)
    if args.action in {"verify", "all"}:
        verify(args.profile)


if __name__ == "__main__":
    main()
