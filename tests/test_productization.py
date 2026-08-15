import csv
import json
from pathlib import Path

import pytest

from src.artifacts import deterministic_run_id, write_run_artifacts
from src.batch import run_sweep
from src.cli import main
from src.configuration import ConfigurationError, load_experiment_config
from src.simulation.runner import run_closed_loop_scenario


ROOT = Path(__file__).resolve().parents[1]


def write_config(path, output_directory):
    path.write_text(
        f'''[experiment]
name = "integration"
seed = 7

[scenario]
preset = "closed_loop_resolved"

[protocol]
name = "centralized"

[output]
directory = "{output_directory}"
'''
    )


def scientific_metrics(result):
    metrics = dict(result["metrics"])
    metrics.pop("runtime_seconds")
    return metrics


def test_cli_help_describes_config_workflow(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["run", "--help"])
    assert exit_info.value.code == 0
    assert "experiment TOML" in capsys.readouterr().out


def test_all_example_experiment_configs_validate():
    for path in sorted((ROOT / "examples").glob("*.toml")):
        if path.name != "network-sweep.toml":
            load_experiment_config(path)


def test_invalid_packet_loss_has_actionable_error(tmp_path):
    path = tmp_path / "bad.toml"
    write_config(path, tmp_path / "results")
    path.write_text(path.read_text() + "\n[network]\npacket_loss_rate = 1.1\n")
    with pytest.raises(ConfigurationError, match=r"network.packet_loss_rate.*<= 1.0"):
        load_experiment_config(path)


def test_missing_config_has_actionable_error(tmp_path):
    with pytest.raises(ConfigurationError, match="Configuration file not found"):
        load_experiment_config(tmp_path / "missing.toml")


def test_run_artifacts_are_complete_and_resolved_config_is_reusable(tmp_path):
    path = tmp_path / "run.toml"
    write_config(path, tmp_path / "results")
    config = load_experiment_config(path)
    result = run_closed_loop_scenario(config.scenario, config.protocol)
    run_directory, summary = write_run_artifacts(config, result)

    assert {item.name for item in run_directory.iterdir()} == {
        "config.toml", "summary.json", "metrics.csv", "events.jsonl", "metadata.json"
    }
    assert summary["run_id"] == deterministic_run_id(config)
    reloaded = load_experiment_config(run_directory / "config.toml")
    assert reloaded.resolved_dict() == config.resolved_dict()
    assert json.loads((run_directory / "summary.json").read_text())["metrics"]["resolved_conjunctions"] == 1
    assert list(csv.DictReader((run_directory / "metrics.csv").open()))[0]["protocol"] == "centralized"


def test_closed_loop_scientific_results_repeat_for_same_config():
    config = load_experiment_config(ROOT / "examples" / "network-degradation.toml")
    first = run_closed_loop_scenario(config.scenario, config.protocol)
    second = run_closed_loop_scenario(config.scenario, config.protocol)
    assert scientific_metrics(first) == scientific_metrics(second)
    assert first["maneuver_proposals"] == second["maneuver_proposals"]
    assert first["risk_outcomes"] == second["risk_outcomes"]


def test_safety_rejection_example_does_not_execute():
    config = load_experiment_config(ROOT / "examples" / "safety-rejection.toml")
    result = run_closed_loop_scenario(config.scenario, config.protocol)
    assert result["metrics"]["safety_validation_failures"] == 1
    assert result["metrics"]["maneuvers_rejected"] == 1
    assert result["metrics"]["maneuvers_executed"] == 0


def test_registered_example_protocol_runs_through_public_selection():
    config = load_experiment_config(
        ROOT / "examples" / "basic.toml",
        overrides={"protocol.name": "example-lowest-id"},
    )
    result = run_closed_loop_scenario(config.scenario, config.protocol)
    assert result["protocol"] == "example-lowest-id"
    assert result["metrics"]["maneuvers_executed"] == 1


def test_sweep_writes_individual_runs_and_aggregate(tmp_path):
    base = tmp_path / "base.toml"
    write_config(base, tmp_path / "results")
    sweep = tmp_path / "sweep.toml"
    sweep.write_text('''[sweep]
base_config = "base.toml"

[sweep.grid]
"protocol.name" = ["centralized", "greedy"]
"experiment.seed" = [1, 2]
''')
    directory, records = run_sweep(sweep, progress=lambda _: None)
    assert len(records) == 4
    assert all(record["status"] == "completed" for record in records)
    assert (directory / "aggregate.csv").is_file()
    assert len(list((tmp_path / "results").glob("*/summary.json"))) == 4
