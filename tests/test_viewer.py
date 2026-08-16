import json
from pathlib import Path
import subprocess
import sys
from threading import Thread
from urllib.request import urlopen

import pytest

from src.artifacts import write_run_artifacts
from src.batch import run_sweep
from src.cli import main
from src.configuration import load_experiment_config
from src.simulation.runner import run_closed_loop_scenario
from src.viewer.model import ViewerArtifactError, load_comparison, load_run, load_target, normalize_events
from src.viewer.server import create_server


ROOT = Path(__file__).resolve().parents[1]


def test_base_cli_import_does_not_load_viewer_server():
    completed = subprocess.run(
        [sys.executable, "-c", "import sys, src.cli; assert 'src.viewer.server' not in sys.modules"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def make_run(tmp_path, example="basic.toml", protocol=None):
    overrides = {"output.directory": str(tmp_path)}
    if protocol:
        overrides["protocol.name"] = protocol
    config = load_experiment_config(ROOT / "examples" / example, overrides=overrides)
    result = run_closed_loop_scenario(config.scenario, config.protocol)
    directory, _ = write_run_artifacts(config, result)
    return directory


def test_run_loader_indexes_messages_agents_and_causal_events(tmp_path):
    directory = make_run(tmp_path, "network-degradation.toml")
    run = load_run(directory)

    assert run["artifact_schema_version"] == 2
    assert {message["status"] for message in run["messages"]} == {"delivered", "dropped"}
    assert {message.get("drop_reason") for message in run["messages"]} == {None, "PACKET_LOSS"}
    assert any(agent["snapshots"] for agent in run["agents"])
    proposal = next(event for event in run["events"] if event["event_type"] == "MANEUVER_PROPOSED")
    related_types = {
        event["event_type"]
        for event in run["events"]
        if event["event_id"] in proposal["related_event_ids"]
    }
    assert {"MANEUVER_VALIDATED", "MANEUVER_EXECUTED", "RISK_REASSESSED"} <= related_types


def test_trace_records_protocol_inputs_and_agent_knowledge(tmp_path):
    run = load_run(make_run(tmp_path))
    decision = next(event for event in run["events"] if event["event_type"] == "PROTOCOL_DECISION")
    snapshots = [event for event in run["events"] if event["event_type"] == "AGENT_STATE_UPDATED"]

    assert decision["payload"]["inputs"]["global_access"] is True
    assert decision["payload"]["inputs"]["visible_risk_event_ids"] == ["risk-0-1"]
    assert decision["payload"]["rationale"] == [
        {
            "risk_event_id": "risk-0-1",
            "selected_agent_id": "SAT-A",
            "selection_criterion": "lower_mission_priority",
            "outcome": "proposal_created",
        }
    ]
    assert len(snapshots) >= 2
    assert snapshots[0]["payload"]["before"]["known_risk_event_ids"] == []
    assert snapshots[0]["payload"]["after"]["known_risk_event_ids"] == ["risk-0-1"]
    assert snapshots[-1]["payload"]["after"]["fuel_budget"] == 120.0


def test_schema_one_artifacts_remain_viewable(tmp_path):
    directory = make_run(tmp_path)
    metadata_path = directory / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata.pop("artifact_schema_version")
    metadata_path.write_text(json.dumps(metadata))
    event_path = directory / "events.jsonl"
    legacy_events = []
    for line in event_path.read_text().splitlines():
        event = json.loads(line)
        for key in ("category", "actor", "entity_ids", "references"):
            event.pop(key, None)
        if event["event_type"].startswith("MESSAGE_"):
            event["payload"].pop("message_id", None)
        legacy_events.append(event)
    event_path.write_text("\n".join(json.dumps(event) for event in legacy_events) + "\n")

    run = load_run(directory)

    assert run["artifact_schema_version"] == 1
    assert run["messages"]
    assert all(event["category"] for event in run["events"])


def test_missing_corrupt_and_unsupported_artifacts_are_actionable(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ViewerArtifactError, match="Missing run summary"):
        load_run(empty)

    corrupt = make_run(tmp_path / "corrupt")
    (corrupt / "events.jsonl").write_text("not json\n")
    with pytest.raises(ViewerArtifactError, match="Corrupt event trace"):
        load_run(corrupt)

    unsupported = make_run(tmp_path / "unsupported")
    metadata_path = unsupported / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["artifact_schema_version"] = 999
    metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(ViewerArtifactError, match="Unsupported artifact schema version 999"):
        load_run(unsupported)


def test_comparison_reports_configuration_and_metric_divergence(tmp_path):
    left = make_run(tmp_path, "protocol-comparison.toml", "centralized")
    right = make_run(tmp_path, "protocol-comparison.toml", "greedy")
    comparison = load_comparison(left, right)

    assert comparison["kind"] == "comparison"
    assert any(diff["field"] == "protocol.name" for diff in comparison["config_differences"])
    unresolved = next(diff for diff in comparison["metric_differences"] if diff["metric"] == "unresolved_conjunctions")
    assert unresolved["left"] == 0
    assert unresolved["right"] == 1


def test_sweep_loader_discovers_cells_and_underlying_runs(tmp_path):
    base = tmp_path / "base.toml"
    base.write_text(f'''[experiment]
name = "viewer-sweep"
seed = 1
[scenario]
preset = "closed_loop_resolved"
[protocol]
name = "centralized"
[output]
directory = "{tmp_path / 'results'}"
''')
    sweep = tmp_path / "viewer-sweep.toml"
    sweep.write_text('''[sweep]
base_config = "base.toml"
[sweep.grid]
"protocol.name" = ["centralized", "greedy"]
"network.packet_loss_rate" = [0.0, 1.0]
''')
    directory, _ = run_sweep(sweep, progress=lambda _: None)

    view = load_target(directory)

    assert view["kind"] == "sweep"
    assert view["parameters"] == ["network.packet_loss_rate", "protocol.name"]
    assert len(view["records"]) == 4
    assert all(record["run_available"] for record in view["records"])


def test_viewer_http_api_and_packaged_frontend_smoke(tmp_path):
    directory = make_run(tmp_path)
    try:
        server = create_server(directory)
    except PermissionError:
        pytest.skip("Local sandbox does not permit binding a loopback test server")
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        manifest = json.loads(urlopen(f"http://127.0.0.1:{port}/api/manifest").read())
        html = urlopen(f"http://127.0.0.1:{port}/").read().decode()
        script = urlopen(f"http://127.0.0.1:{port}/app.js").read().decode()
        temporal = urlopen(f"http://127.0.0.1:{port}/temporal.js").read().decode()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert manifest["kind"] == "run"
    assert "Experiment Viewer" in html
    assert 'src="/temporal.js"' in html
    assert "drawTimeline" in script
    assert "renderInspector" in script
    assert "renderComparisonEvidence" in script
    assert "trajectoryStateAtCursor" in temporal
    assert "messagesAtCursor" in temporal


def test_view_cli_passes_read_only_server_options(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("src.viewer.server.serve_viewer", lambda *args, **kwargs: calls.append((args, kwargs)))

    assert main(["view", str(tmp_path), "--compare", str(tmp_path / "other"), "--host", "localhost", "--port", "8123", "--no-open"]) == 0
    assert calls == [((str(tmp_path),), {"compare": str(tmp_path / "other"), "host": "localhost", "port": 8123, "open_browser": False})]


def test_v2_trace_events_repeat_exactly_for_same_seed():
    config = load_experiment_config(ROOT / "examples" / "viewer-demo.toml")
    first = run_closed_loop_scenario(config.scenario, config.protocol)
    second = run_closed_loop_scenario(config.scenario, config.protocol)

    assert first["trace"]["events"] == second["trace"]["events"]


def test_large_causal_index_caps_per_event_relationships():
    events = [
        {
            "time": index // 10,
            "sequence": index,
            "event_type": "RISK_REASSESSED",
            "payload": {"risk_event_id": "risk-shared"},
            "references": {"risk_event_id": "risk-shared"},
        }
        for index in range(1000)
    ]

    normalized = normalize_events(events)

    assert len(normalized) == 1000
    assert max(len(event["related_event_ids"]) for event in normalized) <= 100
