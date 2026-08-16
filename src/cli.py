"""External command-line interface for Themis experiments."""

import argparse
import csv
import json
from pathlib import Path
import sys

from src.artifacts import write_run_artifacts
from src.analysis import AnalysisError, analyze_sweep
from src.batch import run_sweep
from src.configuration import ConfigurationError, load_experiment_config
from src.protocols.registry import available_protocols
from src.simulation.runner import run_closed_loop_scenario
from src.version import __version__


def _parser():
    parser = argparse.ArgumentParser(
        prog="themis",
        description="Run deterministic autonomous-coordination experiments under communication, execution, and safety constraints.",
        epilog="Themis is a research testbed, not an operational flight-safety system.",
    )
    parser.add_argument("--version", action="version", version=f"Themis {__version__}")
    parser.add_argument("--debug", action="store_true", help="Show tracebacks for configuration and runtime errors.")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="Run one validated TOML experiment and write a structured run directory.")
    run.add_argument("config", help="Path to an experiment TOML file.")
    run.add_argument("--protocol", choices=available_protocols(), help="Override protocol.name for this run.")
    run.add_argument("--seed", type=int, help="Override experiment.seed for this run.")
    run.add_argument("--output-dir", help="Override output.directory (resolved relative to the config file).")

    compare = commands.add_parser("compare", help="Run the same config with two or more protocols and write comparison.csv.")
    compare.add_argument("config", help="Path to a base experiment TOML file.")
    compare.add_argument("--protocol", action="append", choices=available_protocols(), required=True, help="Protocol to include; repeat this option.")

    sweep = commands.add_parser("sweep", help="Run a TOML parameter grid; completed run IDs are resumable.")
    sweep.add_argument("config", help="Path to a sweep TOML file.")

    analyze = commands.add_parser("analyze", help="Compute replicate-aware statistics for a completed sweep.")
    analyze.add_argument("path", help="Sweep directory or aggregate.json path.")
    analyze.add_argument("--group-by", action="append", help="Aggregate field defining a condition; repeat as needed.")
    analyze.add_argument("--metric", action="append", help="Numeric metric to summarize; repeat as needed.")
    analyze.add_argument("--output-dir", help="Analysis output directory (default: <sweep>/analysis).")

    validate = commands.add_parser("validate", help="Validate and resolve an experiment config without running it.")
    validate.add_argument("config", help="Path to an experiment TOML file.")

    replay = commands.add_parser("replay", help="Print ordered events from a run directory or events.jsonl.")
    replay.add_argument("path", help="Run directory or events.jsonl path.")

    view = commands.add_parser("view", help="Open a completed run, comparison, or sweep in the local visual debugger.")
    view.add_argument("path", help="Path to a run, comparison, or sweep directory.")
    view.add_argument("--compare", help="Optional second run directory for synchronized comparison.")
    view.add_argument("--host", default="127.0.0.1", help="Local bind address (default: 127.0.0.1).")
    view.add_argument("--port", type=int, default=0, help="Local port; 0 chooses an available port.")
    view.add_argument("--no-open", action="store_true", help="Serve without opening a browser.")
    return parser


def _overrides(args):
    values = {}
    if getattr(args, "protocol", None) and isinstance(args.protocol, str):
        values["protocol.name"] = args.protocol
    if getattr(args, "seed", None) is not None:
        values["experiment.seed"] = args.seed
    if getattr(args, "output_dir", None):
        values["output.directory"] = args.output_dir
    return values


def _print_run(summary, directory):
    metrics = summary["metrics"]
    print(f"Run: {summary['run_id']}")
    print(f"Benchmark: {summary['benchmark']}")
    print(f"Scenario / protocol / seed: {summary['scenario']} / {summary['protocol']} / {summary['seed']}")
    print(f"Outcome: {summary['outcome']}")
    print(f"Safety: {metrics['original_conjunctions']} initial, {metrics['resolved_conjunctions']} resolved, {metrics['unresolved_conjunctions']} unresolved, {metrics['safety_validation_failures']} validator rejection(s)")
    print(f"Communication: {metrics['messages_sent']} sent, {metrics['messages_delivered']} delivered, {metrics['messages_dropped']} dropped")
    print(f"Maneuvers: {metrics['maneuvers_executed']} executed, {metrics['total_delta_v_used_km_per_step']} km/step delta-v proxy")
    print(f"Artifacts: {directory}")


def _run(args):
    config = load_experiment_config(args.config, overrides=_overrides(args))
    result = run_closed_loop_scenario(config.scenario, config.protocol)
    directory, summary = write_run_artifacts(config, result)
    _print_run(summary, directory)


def _compare(args):
    if len(set(args.protocol)) < 2:
        raise ConfigurationError("Protocol comparison requires at least two distinct --protocol values.")
    records = []
    output_directory = None
    for name in dict.fromkeys(args.protocol):
        config = load_experiment_config(args.config, overrides={"protocol.name": name})
        result = run_closed_loop_scenario(config.scenario, config.protocol)
        directory, summary = write_run_artifacts(config, result)
        output_directory = config.output_directory / f"{Path(args.config).stem}-comparison"
        records.append({"run_id": summary["run_id"], "protocol": name, **summary["metrics"]})
        print(f"Completed {name}: {directory}")
    output_directory.mkdir(parents=True, exist_ok=True)
    columns = sorted({key for record in records for key in record})
    with (output_directory / "comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)
    (output_directory / "comparison.json").write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Comparison: {output_directory / 'comparison.csv'}")


def _replay(path):
    event_path = Path(path)
    if event_path.is_dir():
        event_path = event_path / "events.jsonl"
    if not event_path.is_file():
        raise ConfigurationError(f"Event file not found: {event_path}")
    for line in event_path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        print(f"{event['time']:>4} #{event['sequence']:>3} {event['event_type']} {event.get('payload', {})}")


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            _run(args)
        elif args.command == "compare":
            _compare(args)
        elif args.command == "sweep":
            directory, records = run_sweep(args.config)
            failures = sum(record["status"] == "failed" for record in records)
            print(f"Aggregate: {directory / 'aggregate.csv'} ({failures} failure(s))")
            if failures:
                return 1
        elif args.command == "analyze":
            directory, analysis = analyze_sweep(
                args.path,
                group_by=args.group_by,
                metrics=args.metric,
                output_directory=args.output_dir,
            )
            print(
                f"Analysis: {directory / 'analysis.csv'} "
                f"({len(analysis['rows'])} condition/metric row(s))"
            )
        elif args.command == "validate":
            config = load_experiment_config(args.config)
            print(json.dumps(config.resolved_dict(), indent=2, sort_keys=True))
            print("Configuration is valid.")
        elif args.command == "replay":
            _replay(args.path)
        elif args.command == "view":
            from src.viewer.server import serve_viewer
            serve_viewer(args.path, compare=args.compare, host=args.host, port=args.port, open_browser=not args.no_open)
    except (AnalysisError, ConfigurationError, OSError, ValueError, json.JSONDecodeError) as error:
        if args.debug:
            raise
        print(f"Error: {error}", file=sys.stderr)
        print("Run with --debug for a traceback. See docs/configuration.md.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
