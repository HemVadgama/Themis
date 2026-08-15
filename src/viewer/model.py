"""Load, validate, normalize, and index Themis viewer artifacts."""

from collections import defaultdict, deque
from bisect import bisect_left
from copy import deepcopy
import csv
import json
from pathlib import Path
import tomllib

from src.simulation.trace import EVENT_CATEGORIES


SUPPORTED_ARTIFACT_SCHEMA_VERSION = 2


class ViewerArtifactError(ValueError):
    """A completed-run artifact cannot be safely interpreted by the viewer."""


EVENT_TITLES = {
    "RUN_STARTED": "Experiment started",
    "RUN_COMPLETED": "Experiment completed",
    "STATE_UPDATED": "Physical truth initialized",
    "AGENT_STATE_UPDATED": "Agent belief updated",
    "CONJUNCTION_DETECTED": "Conjunction detected",
    "CONJUNCTION_RESOLVED": "Conjunction resolved",
    "RISK_REASSESSED": "Risk reassessed",
    "SECONDARY_CONJUNCTION_DETECTED": "Secondary risk detected",
    "MESSAGE_SENT": "Message sent",
    "MESSAGE_DELIVERED": "Message delivered",
    "MESSAGE_DROPPED": "Message dropped",
    "MESSAGE_DELAYED_BEYOND_USEFULNESS": "Message arrived too late",
    "PROTOCOL_DECISION": "Protocol decision",
    "COORDINATION_TIMEOUT": "Coordination timed out",
    "MANEUVER_PROPOSED": "Action proposed",
    "MANEUVER_VALIDATED": "Safety validation passed",
    "MANEUVER_REJECTED": "Safety validation rejected",
    "MANEUVER_ACCEPTED": "Action accepted",
    "MANEUVER_SCHEDULED": "Action scheduled",
    "MANEUVER_EXECUTED": "Action executed",
    "MANEUVER_FAILED": "Action execution failed",
    "TRAJECTORY_REPROPAGATED": "Physical trajectory updated",
    "RESOURCE_UPDATED": "Resource state updated",
}


def _read_json(path, label, required=True):
    if not path.is_file():
        if required:
            raise ViewerArtifactError(f"Missing {label}: {path}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ViewerArtifactError(f"Corrupt {label} at {path}: {error}") from error
    if not isinstance(value, (dict, list)):
        raise ViewerArtifactError(f"Invalid {label} at {path}: expected a JSON object or array.")
    return value


def _read_events(path):
    if not path.is_file():
        raise ViewerArtifactError(f"Missing event trace: {path}")
    events = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise ViewerArtifactError(f"Corrupt event trace at {path}, line {line_number}: {error}") from error
        if not isinstance(event, dict) or not {"time", "sequence", "event_type"}.issubset(event):
            raise ViewerArtifactError(f"Invalid event trace at {path}, line {line_number}: require time, sequence, and event_type.")
        events.append(event)
    events.sort(key=lambda event: (event["time"], event["sequence"]))
    return events


def _reference_values(event):
    return {value for value in event.get("references", {}).values() if value}


def normalize_events(raw_events):
    """Normalize schema-v1/v2 events and construct deterministic causal links."""
    events = []
    pending_messages = defaultdict(deque)
    latest_maneuver = None
    latest_risk = None
    known_risks = defaultdict(set)

    for raw in raw_events:
        event = deepcopy(raw)
        event_type = event["event_type"]
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        references = dict(event.get("references") or {})
        for key in ("message_id", "maneuver_id", "risk_event_id"):
            if payload.get(key):
                references.setdefault(key, payload[key])
        maneuver = payload.get("maneuver")
        if isinstance(maneuver, dict):
            for key in ("maneuver_id", "risk_event_id"):
                if maneuver.get(key):
                    references.setdefault(key, maneuver[key])

        if event_type == "CONJUNCTION_DETECTED":
            latest_risk = payload.get("risk_event_id", latest_risk)
        if event_type == "MANEUVER_PROPOSED":
            latest_maneuver = payload.get("maneuver_id", latest_maneuver)
            latest_risk = payload.get("risk_event_id", latest_risk)
        if event_type.startswith("MANEUVER_") and latest_maneuver:
            references.setdefault("maneuver_id", latest_maneuver)
        if event_type in {"MANEUVER_VALIDATED", "MANEUVER_REJECTED", "MANEUVER_ACCEPTED", "MANEUVER_SCHEDULED", "MANEUVER_EXECUTED", "MANEUVER_FAILED", "TRAJECTORY_REPROPAGATED", "RESOURCE_UPDATED", "RISK_REASSESSED", "CONJUNCTION_RESOLVED"} and latest_risk:
            references.setdefault("risk_event_id", latest_risk)

        if event_type in {"MESSAGE_SENT", "MESSAGE_DROPPED"}:
            message_id = payload.get("message_id") or f"legacy-msg-{event['sequence']:06d}"
            references["message_id"] = message_id
            payload.setdefault("message_id", message_id)
            payload.setdefault("sender_id", "GROUND_TRUTH_MONITOR")
            if event_type == "MESSAGE_SENT":
                key = (payload.get("recipient_id"), payload.get("message_type"))
                pending_messages[key].append((message_id, payload.get("risk_event_id")))
        elif event_type in {"MESSAGE_DELIVERED", "MESSAGE_DELAYED_BEYOND_USEFULNESS"} and not references.get("message_id"):
            key = (payload.get("recipient_id"), payload.get("message_type"))
            if pending_messages[key]:
                message_id, risk_id = pending_messages[key].popleft()
                references["message_id"] = message_id
                payload.setdefault("message_id", message_id)
                if risk_id:
                    references.setdefault("risk_event_id", risk_id)
                    payload.setdefault("risk_event_id", risk_id)

        actor = event.get("actor") or payload.get("agent_id") or payload.get("sender_id")
        entities = list(event.get("entity_ids") or [])
        for key in ("agent_id", "recipient_id", "satellite_a", "satellite_b"):
            value = payload.get(key)
            if value and value not in entities:
                entities.append(value)
        event.update({
            "event_id": event.get("event_id", f"evt-{event['sequence']:06d}"),
            "category": event.get("category") or EVENT_CATEGORIES.get(event_type, "other"),
            "title": EVENT_TITLES.get(event_type, event_type.replace("_", " ").title()),
            "actor": actor,
            "entity_ids": entities,
            "references": references,
            "payload": payload,
        })
        events.append(event)

        if event_type in {"MESSAGE_DELIVERED", "MESSAGE_DELAYED_BEYOND_USEFULNESS"}:
            agent_id = payload.get("recipient_id")
            risk_id = references.get("risk_event_id")
            if agent_id and risk_id:
                known_risks[agent_id].add(risk_id)
                event["derived_agent_knowledge"] = {
                    "agent_id": agent_id,
                    "known_risk_event_ids": sorted(known_risks[agent_id]),
                    "source": "derived from delivered risk alerts" if raw.get("category") is None else "recorded trace linkage",
                }

    by_reference = defaultdict(list)
    for event in events:
        for value in _reference_values(event):
            by_reference[value].append(event["event_id"])
    event_order = {event["event_id"]: index for index, event in enumerate(events)}
    reference_orders = {
        value: [event_order[event_id] for event_id in bucket]
        for value, bucket in by_reference.items()
        if len(bucket) > 100
    }
    for event in events:
        related = set()
        for value in _reference_values(event):
            bucket = by_reference[value]
            if len(bucket) <= 100:
                related.update(bucket)
                continue
            center = bisect_left(reference_orders[value], event_order[event["event_id"]])
            related.update(bucket[:20])
            related.update(bucket[max(0, center - 30):center + 31])
            related.update(bucket[-20:])
        related.discard(event["event_id"])
        event["related_event_ids"] = sorted(related, key=lambda event_id: int(event_id.rsplit("-", 1)[-1]))
    return events


def _agent_index(events, config):
    agents = {}
    scenario = config.get("scenario", {})
    initial_states = scenario.get("initial_states", [])
    fuel_budgets = scenario.get("fuel_budgets", {})
    default_fuel = config.get("maneuver", {}).get("default_fuel_budget", 0.0)
    for state in initial_states:
        agent_id = state.get("agent_id")
        if agent_id:
            agents[agent_id] = {
                "agent_id": agent_id,
                "initial_position_km": state.get("position_km"),
                "initial_velocity_km_per_step": state.get("velocity_km_per_step"),
                "snapshots": [{"time": 0, "sequence": -1, "known_risk_event_ids": [], "fuel_budget": fuel_budgets.get(agent_id, default_fuel), "source": "resolved config"}],
            }
    for event in events:
        if event["event_type"] == "AGENT_STATE_UPDATED":
            after = event["payload"].get("after", {})
            agent_id = after.get("agent_id") or event.get("actor")
            if agent_id:
                agents.setdefault(agent_id, {"agent_id": agent_id, "snapshots": []})["snapshots"].append({"time": event["time"], "sequence": event["sequence"], **after, "source": "recorded agent snapshot"})
        elif event.get("derived_agent_knowledge"):
            snapshot = event["derived_agent_knowledge"]
            agent_id = snapshot["agent_id"]
            agents.setdefault(agent_id, {"agent_id": agent_id, "snapshots": []})["snapshots"].append({"time": event["time"], "sequence": event["sequence"], **snapshot})
    return [agents[key] for key in sorted(agents)]


def _message_index(events):
    messages = {}
    for event in events:
        message_id = event.get("references", {}).get("message_id")
        if not message_id:
            continue
        record = messages.setdefault(message_id, {"message_id": message_id, "events": []})
        payload = event["payload"]
        for key in ("message_type", "sender_id", "recipient_id", "risk_event_id", "sent_time", "deliver_at", "delivered_time", "latency_steps", "drop_reason"):
            if payload.get(key) is not None:
                record[key] = payload[key]
        record["events"].append(event["event_id"])
        if event["event_type"] == "MESSAGE_DROPPED":
            record["status"] = "dropped"
        elif event["event_type"] == "MESSAGE_DELAYED_BEYOND_USEFULNESS":
            record["status"] = "late"
        elif event["event_type"] == "MESSAGE_DELIVERED":
            record["status"] = "delivered"
        else:
            record.setdefault("status", "sent")
    return list(messages.values())


def load_run(path):
    run_path = Path(path).expanduser().resolve()
    if not run_path.is_dir():
        raise ViewerArtifactError(f"Run directory not found: {run_path}")
    summary = _read_json(run_path / "summary.json", "run summary")
    if not isinstance(summary, dict) or not {"run_id", "protocol", "seed", "metrics"}.issubset(summary):
        raise ViewerArtifactError(f"Invalid run summary at {run_path / 'summary.json'}: missing run_id, protocol, seed, or metrics.")
    metadata = _read_json(run_path / "metadata.json", "run metadata", required=False)
    schema_version = metadata.get("artifact_schema_version", 1)
    if not isinstance(schema_version, int) or schema_version < 1:
        raise ViewerArtifactError(f"Invalid artifact schema version: {schema_version!r}.")
    if schema_version > SUPPORTED_ARTIFACT_SCHEMA_VERSION:
        raise ViewerArtifactError(f"Unsupported artifact schema version {schema_version}; this viewer supports up to {SUPPORTED_ARTIFACT_SCHEMA_VERSION}.")
    config_path = run_path / "config.toml"
    if not config_path.is_file():
        raise ViewerArtifactError(f"Missing resolved configuration: {config_path}")
    try:
        config_text = config_path.read_text(encoding="utf-8")
        config = tomllib.loads(config_text)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ViewerArtifactError(f"Corrupt resolved configuration at {config_path}: {error}") from error
    events = normalize_events(_read_events(run_path / "events.jsonl"))
    categories = sorted({event["category"] for event in events})
    return {
        "kind": "run",
        "artifact_schema_version": schema_version,
        "viewer_schema_version": SUPPORTED_ARTIFACT_SCHEMA_VERSION,
        "benchmark": "spacecraft-coordination",
        "path": str(run_path),
        "summary": summary,
        "metadata": metadata,
        "config": config,
        "config_text": config_text,
        "events": events,
        "event_categories": categories,
        "messages": _message_index(events),
        "agents": _agent_index(events, config),
        "reproduction_command": f"themis run {run_path / 'config.toml'}",
    }


def _flatten(value, prefix=""):
    result = {}
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else key
            result.update(_flatten(item, child))
    else:
        result[prefix] = value
    return result


def load_comparison(left_path, right_path):
    left = load_run(left_path)
    right = load_run(right_path)
    left_config = _flatten(left["config"])
    right_config = _flatten(right["config"])
    ignored = {"output.directory"}
    config_differences = [
        {"field": key, "left": left_config.get(key), "right": right_config.get(key)}
        for key in sorted(set(left_config) | set(right_config))
        if key not in ignored and left_config.get(key) != right_config.get(key)
    ]
    left_metrics = left["summary"]["metrics"]
    right_metrics = right["summary"]["metrics"]
    metric_differences = []
    for key in sorted(set(left_metrics) | set(right_metrics)):
        first, second = left_metrics.get(key), right_metrics.get(key)
        delta = second - first if isinstance(first, (int, float)) and not isinstance(first, bool) and isinstance(second, (int, float)) and not isinstance(second, bool) else None
        if first != second:
            metric_differences.append({"metric": key, "left": first, "right": second, "delta": delta})
    return {"kind": "comparison", "runs": [left, right], "config_differences": config_differences, "metric_differences": metric_differences}


def _run_path_for_id(container, run_id):
    if not isinstance(run_id, str) or not run_id or "/" in run_id or "\\" in run_id:
        return None
    candidate = (container.parent / run_id).resolve()
    return candidate if candidate.parent == container.parent and candidate.is_dir() else None


def load_sweep_view(path):
    sweep_path = Path(path).expanduser().resolve()
    records = _read_json(sweep_path / "aggregate.json", "sweep aggregate")
    if not isinstance(records, list):
        raise ViewerArtifactError(f"Invalid sweep aggregate at {sweep_path / 'aggregate.json'}: expected an array.")
    parameters = sorted({key for record in records if isinstance(record, dict) for key in record if "." in key})
    enriched = []
    for record in records:
        item = dict(record)
        run_path = _run_path_for_id(sweep_path, item.get("run_id"))
        item["run_available"] = run_path is not None
        item["run_path"] = str(run_path) if run_path else None
        enriched.append(item)
    return {"kind": "sweep", "path": str(sweep_path), "records": enriched, "parameters": parameters}


def load_comparison_directory(path):
    directory = Path(path).expanduser().resolve()
    records = _read_json(directory / "comparison.json", "comparison aggregate")
    if not isinstance(records, list) or len(records) < 2:
        raise ViewerArtifactError("Comparison aggregate must contain at least two runs.")
    paths = [_run_path_for_id(directory, record.get("run_id")) for record in records[:2]]
    if any(path is None for path in paths):
        raise ViewerArtifactError("Comparison run directories could not be found beside the comparison directory.")
    return load_comparison(paths[0], paths[1])


def load_target(path, compare=None):
    target = Path(path).expanduser().resolve()
    if compare:
        return load_comparison(target, compare)
    if (target / "summary.json").is_file():
        return load_run(target)
    if (target / "aggregate.json").is_file():
        return load_sweep_view(target)
    if (target / "comparison.json").is_file():
        return load_comparison_directory(target)
    raise ViewerArtifactError(f"Unsupported viewer target: {target}. Expected a run, comparison, or sweep directory.")
