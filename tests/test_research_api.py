import csv
import json
from pathlib import Path

import pytest

from src.analysis import AnalysisError, analyze_sweep
from src.configuration import load_experiment_config
from src.protocols.base import ProtocolDecision
from src.protocols import registry
from src.simulation.runner import run_closed_loop_scenario
from src.artifacts import write_run_artifacts
from themis.artifacts import load_run, schema_path
from themis.protocols import check_protocol


ROOT = Path(__file__).resolve().parents[1]


class ExternalProtocol:
    name = "external-test"

    def decide(self, world, conjunctions):
        return ProtocolDecision(unresolved_conjunctions=len(conjunctions))

    def propose_maneuvers(self, context):
        return ProtocolDecision(unresolved_conjunctions=len(context.risk_events))


class FakeEntryPoint:
    name = "external-test"
    value = "research_protocols:ExternalProtocol"

    def load(self):
        return ExternalProtocol


class ConflictingEntryPoint(FakeEntryPoint):
    value = "other_package:ExternalProtocol"


class FakeEntryPoints(list):
    def select(self, *, group):
        return self if group == "themis.protocols" else []


def test_installed_protocol_entry_point_is_discovered_and_checked(monkeypatch):
    monkeypatch.setattr(registry.metadata, "entry_points", lambda: FakeEntryPoints([FakeEntryPoint()]))
    assert "external-test" in registry.available_protocols()
    assert isinstance(registry.make_protocol("external-test"), ExternalProtocol)


def test_duplicate_installed_protocol_names_are_rejected(monkeypatch):
    monkeypatch.setattr(
        registry.metadata,
        "entry_points",
        lambda: FakeEntryPoints([FakeEntryPoint(), ConflictingEntryPoint()]),
    )
    with pytest.raises(ValueError, match="Multiple installed distributions"):
        registry.make_protocol("external-test")


def test_protocol_contract_reports_missing_methods():
    with pytest.raises(TypeError, match=r"must implement propose_maneuvers"):
        check_protocol(type("Incomplete", (), {"name": "incomplete", "decide": lambda *_: None})())


def test_public_artifact_reader_streams_events_and_exposes_schemas(tmp_path):
    config = load_experiment_config(
        ROOT / "examples" / "basic.toml",
        overrides={"output.directory": str(tmp_path)},
    )
    run_directory, _ = write_run_artifacts(
        config,
        run_closed_loop_scenario(config.scenario, config.protocol),
    )
    run = load_run(run_directory)
    assert run.summary["benchmark"] == "spacecraft-coordination-v1"
    assert next(run.events())["event_type"] == "RUN_STARTED"
    for name in ("metadata-v2.schema.json", "summary-v2.schema.json", "event-v2.schema.json", "analysis-v1.schema.json"):
        assert json.loads(schema_path(name).read_text())["$schema"].endswith("2020-12/schema")


def test_resolved_config_preserves_selected_preset():
    config = load_experiment_config(ROOT / "examples" / "protocol-comparison.toml")
    assert config.resolved_dict()["scenario"]["preset"] == "closed_loop_protocol_difference"


def test_sweep_analysis_groups_replicates_and_writes_machine_readable_results(tmp_path):
    records = [
        {"status": "completed", "protocol.name": "a", "experiment.seed": 1, "seed": 1, "resolved_conjunctions": 1, "runtime_seconds": 8.0},
        {"status": "completed", "protocol.name": "a", "experiment.seed": 2, "seed": 2, "resolved_conjunctions": 3, "runtime_seconds": 9.0},
        {"status": "completed", "protocol.name": "b", "experiment.seed": 1, "seed": 1, "resolved_conjunctions": 4, "runtime_seconds": 7.0},
        {"status": "failed", "protocol.name": "a", "experiment.seed": 3, "error": "expected test failure"},
    ]
    sweep = tmp_path / "aggregate.json"
    sweep.write_text(json.dumps(records))
    directory, payload = analyze_sweep(sweep, metrics=["resolved_conjunctions"])
    row_a = next(row for row in payload["rows"] if row["protocol.name"] == "a")
    assert row_a["n"] == 2
    assert row_a["seed_count"] == 2
    assert row_a["mean"] == 2.0
    assert row_a["sample_sd"] == pytest.approx(2**0.5)
    assert row_a["ci95_low"] == pytest.approx(2.0 - 12.706)
    assert (directory / "analysis.json").is_file()
    assert len(list(csv.DictReader((directory / "analysis.csv").open()))) == 2


def test_sweep_analysis_rejects_unsupported_confidence_level(tmp_path):
    aggregate = tmp_path / "aggregate.json"
    aggregate.write_text(json.dumps([{"status": "completed", "seed": 1, "value": 2}]))
    with pytest.raises(AnalysisError, match="Only confidence=0.95"):
        analyze_sweep(aggregate, metrics=["value"], confidence=0.9)
