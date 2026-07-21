from copy import deepcopy
import json

from src.simulation.runner import run_closed_loop_scenario
from src.simulation.scenario import load_scenario


def normalize_result(result):
    normalized = deepcopy(result)
    normalized["metrics"]["runtime_seconds"] = 0.0
    for event in normalized["trace"]["events"]:
        if event["event_type"] == "RUN_COMPLETED":
            event["payload"]["metrics"]["runtime_seconds"] = 0.0
    return normalized


def test_closed_loop_valid_maneuver_resolves_conjunction():
    result = run_closed_loop_scenario(load_scenario("closed_loop_resolved", seed=42), "centralized")

    assert result["metrics"]["original_conjunctions"] == 1
    assert result["metrics"]["maneuvers_proposed"] == 1
    assert result["metrics"]["maneuvers_executed"] == 1
    assert result["metrics"]["resolved_conjunctions"] == 1
    assert result["risk_outcomes"][0]["outcome"] == "RESOLVED"


def test_closed_loop_invalid_maneuver_is_rejected_for_budget():
    result = run_closed_loop_scenario(load_scenario("closed_loop_insufficient_fuel", seed=42), "centralized")

    assert result["metrics"]["maneuvers_executed"] == 0
    assert result["metrics"]["safety_validation_failures"] == 1
    assert result["metrics"]["unresolved_conjunctions"] == 1
    assert result["maneuver_proposals"][0]["rejection_reason"] == "INSUFFICIENT_FUEL"


def test_packet_latency_prevents_greedy_agreement_and_triggers_fallback():
    result = run_closed_loop_scenario(load_scenario("closed_loop_late_response", seed=42), "greedy")

    assert result["metrics"]["maneuvers_proposed"] == 0
    assert result["metrics"]["timeouts"] == 1
    assert result["metrics"]["fallback_activations"] == 1
    assert result["metrics"]["unresolved_conjunctions"] == 1


def test_packet_loss_prevents_greedy_agreement_and_triggers_fallback():
    result = run_closed_loop_scenario(load_scenario("closed_loop_packet_loss", seed=42), "greedy")

    assert result["metrics"]["maneuvers_proposed"] == 0
    assert result["metrics"]["messages_dropped"] == 2
    assert result["metrics"]["fallback_activations"] == 1
    assert result["metrics"]["unresolved_conjunctions"] == 1


def test_closed_loop_detects_secondary_conjunction_created_by_maneuver():
    result = run_closed_loop_scenario(load_scenario("closed_loop_secondary", seed=42), "centralized")

    assert result["metrics"]["maneuvers_executed"] == 1
    assert result["metrics"]["secondary_conjunctions_created"] == 1
    assert result["risk_outcomes"][0]["outcome"] == "SECONDARY_RISK_CREATED"


def test_same_closed_loop_scenario_and_seed_are_deterministic():
    config = load_scenario("closed_loop_resolved", seed=7)

    first = normalize_result(run_closed_loop_scenario(config, "centralized"))
    second = normalize_result(run_closed_loop_scenario(config, "centralized"))

    assert first == second


def test_centralized_and_greedy_can_make_different_decisions():
    config = load_scenario("closed_loop_protocol_difference", seed=42)

    centralized = run_closed_loop_scenario(config, "centralized")
    greedy = run_closed_loop_scenario(config, "greedy")

    assert centralized["maneuver_proposals"][0]["agent_id"] != greedy["maneuver_proposals"][0]["agent_id"]
    assert centralized["metrics"]["total_delta_v_used_km_per_step"] != greedy["metrics"]["total_delta_v_used_km_per_step"]


def test_trace_contains_ordered_closed_loop_events():
    result = run_closed_loop_scenario(load_scenario("closed_loop_resolved", seed=42), "centralized")
    events = result["trace"]["events"]

    assert [event["sequence"] for event in events] == list(range(len(events)))
    assert [event["time"] for event in events] == sorted(event["time"] for event in events)
    assert {"MANEUVER_PROPOSED", "MANEUVER_VALIDATED", "MANEUVER_EXECUTED", "RISK_REASSESSED"} <= {
        event["event_type"] for event in events
    }


def test_execution_error_is_seeded_and_serializable():
    result = run_closed_loop_scenario(load_scenario("closed_loop_execution_error", seed=42), "centralized")
    maneuver = result["maneuver_proposals"][0]

    assert maneuver["delta_v_vector_km_per_step"] == [-80.0, 0.0, 0.0]
    assert maneuver["actual_delta_v_vector_km_per_step"] == [-88.0, 0.0, 0.0]
    json.dumps(result, sort_keys=True)


def test_metrics_match_trace_event_counts():
    result = run_closed_loop_scenario(load_scenario("closed_loop_resolved", seed=42), "centralized")
    events = result["trace"]["events"]

    assert result["metrics"]["maneuvers_proposed"] == len(
        [event for event in events if event["event_type"] == "MANEUVER_PROPOSED"]
    )
    assert result["metrics"]["maneuvers_executed"] == len(
        [event for event in events if event["event_type"] == "MANEUVER_EXECUTED"]
    )
