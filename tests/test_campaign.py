from copy import deepcopy

import pytest

from src.network.message import MessageType
from src.artifacts import write_run_artifacts
from src.configuration import load_experiment_config
from src.protocols.base import CampaignProtocolStep
from src.protocols.campaign import check_campaign_step
from src.simulation.campaign import CampaignRunner, run_campaign_scenario
from src.simulation.scenario import load_scenario
from src.simulation.dispatch import run_experiment
from src.simulation.runner import run_closed_loop_scenario
from src.viewer.model import load_run


def scientific(result):
    value = deepcopy(result)
    value["metrics"].pop("runtime_seconds", None)
    value["trace"]["events"] = [
        event for event in value["trace"]["events"]
        if event["event_type"] != "RUN_COMPLETED"
    ]
    return value


def campaign(seed=42, **changes):
    config = load_scenario("campaign_reference", seed=seed)
    for key, value in changes.items():
        setattr(config, key, value)
    return config


def events(result, event_type):
    return [event for event in result["trace"]["events"] if event["event_type"] == event_type]


def test_campaign_is_multi_cycle_persistent_and_creates_causal_secondary_risk():
    result = run_campaign_scenario(campaign(), "centralized")

    assert result["metrics"]["cycles_completed"] == 16
    assert result["metrics"]["maneuver_count"] >= 2
    assert result["metrics"]["secondary_risks_created"] >= 1
    secondary = next(risk for risk in result["risk_events"] if risk["classification"] == "SECONDARY")
    assert secondary["causal_maneuver_id"]
    assert result["metrics"]["per_agent_resource_consumption"]["SAT-A"] > 0


def test_persistent_pair_is_updated_not_recreated_each_cycle():
    result = run_campaign_scenario(campaign(duration_steps=4), "auction")
    pair = [risk for risk in result["risk_events"] if {risk["satellite_a"], risk["satellite_b"]} == {"SAT-A", "SAT-B"}]

    assert len(pair) == 1
    assert len([event for event in events(result, "RISK_UPDATED") if event["references"].get("risk_event_id") == pair[0]["risk_event_id"]]) == 3


def test_successful_auction_is_auditable_and_uses_deterministic_winner_order():
    config = campaign(duration_steps=7)
    config.mission_priorities["SAT-A"] = 1
    config.mission_priorities["SAT-B"] = 1
    result = run_campaign_scenario(config, "auction")

    winner = events(result, "AUCTION_WINNER_SELECTED")[0]
    assert winner["payload"]["winner_id"] == "SAT-A"
    assert winner["payload"]["tie_break"] == "score_then_bidder_id_then_bid_id"
    assert result["metrics"]["bids_expected"] == 2
    assert result["metrics"]["bids_received"] == 2
    assert result["metrics"]["auction_successes"] == 1


def test_bandwidth_can_drop_announcement_and_change_bid_collection():
    result = run_campaign_scenario(campaign(duration_steps=7, bandwidth_limit_per_agent=1), "auction")
    dropped = events(result, "MESSAGE_DROPPED")

    assert any(event["payload"]["message_type"] == "AUCTION_ANNOUNCEMENT" for event in dropped)
    assert result["metrics"]["bids_received"] < result["metrics"]["bids_expected"]


def test_bandwidth_can_drop_a_bid_without_hiding_the_drop():
    result = run_campaign_scenario(campaign(duration_steps=7, bandwidth_limit_per_agent=2), "auction")

    assert any(event["payload"]["message_type"] == "AUCTION_BID" for event in events(result, "MESSAGE_DROPPED"))
    first = [event for event in events(result, "AUCTION_BID_RECEIVED") if event["references"]["risk_event_id"] == "risk:SAT-A:SAT-B:001"]
    assert len(first) == 1


def test_delayed_bid_regime_ends_with_no_valid_bid():
    result = run_campaign_scenario(
        campaign(duration_steps=7, network_latency_steps=1, decision_deadline_steps=4),
        "auction",
    )

    assert result["metrics"]["auction_no_valid_bids"] >= 1
    assert result["metrics"]["auction_successes"] == 0


def test_packet_loss_can_drop_award_and_timeout():
    found = None
    for seed in range(80):
        result = run_campaign_scenario(campaign(seed=seed, duration_steps=7, packet_loss_rate=0.3), "auction")
        if any(event["payload"]["message_type"] == "AUCTION_AWARD" for event in events(result, "MESSAGE_DROPPED")):
            found = result
            break
    assert found is not None
    assert found["metrics"]["auction_timeouts"] >= 1
    assert found["metrics"]["auction_successes"] == 0


def test_insufficient_resource_produces_no_valid_bid():
    config = campaign(duration_steps=7)
    config.fuel_budgets = {agent_id: 5.0 for agent_id in ("SAT-A", "SAT-B", "SAT-C", "SAT-D")}
    result = run_campaign_scenario(config, "auction")

    assert result["metrics"]["auction_no_valid_bids"] >= 1
    assert result["metrics"]["maneuver_count"] == 0


def test_conflicting_simultaneous_auctions_reserve_each_agent_once():
    config = campaign(duration_steps=7)
    config.agent_count = 3
    config.initial_states = [
        {"agent_id": "SAT-A", "position_km": [0.0, 0.0, 0.0], "velocity_km_per_step": [0.0, 0.0, 0.0]},
        {"agent_id": "SAT-B", "position_km": [20.0, 0.0, 0.0], "velocity_km_per_step": [0.0, 0.0, 0.0]},
        {"agent_id": "SAT-C", "position_km": [40.0, 0.0, 0.0], "velocity_km_per_step": [0.0, 0.0, 0.0]},
    ]
    config.mission_priorities = {"SAT-A": 1, "SAT-B": 2, "SAT-C": 3}
    config.fuel_budgets = {}
    result = run_campaign_scenario(config, "auction")
    reservations = events(result, "PROTOCOL_RESOURCE_RESERVED")

    at_zero = [event["payload"]["agent_id"] for event in reservations if event["time"] == 0]
    assert len(at_zero) == len(set(at_zero))
    assert result["metrics"]["auction_no_valid_bids"] >= 1


def test_execution_failure_after_award_releases_actual_reservation():
    result = run_campaign_scenario(campaign(duration_steps=7, execution_failure_rate=1.0), "auction")

    assert result["metrics"]["auction_successes"] == 1
    assert result["metrics"]["execution_failures"] == 1
    final = events(result, "STATE_SNAPSHOT")[-1]["payload"]["truth"]["resources"]
    assert all(value["reserved"] == 0 for value in final.values())


def test_campaign_same_seed_reproduces_and_loss_varies_across_seeds():
    first = scientific(run_campaign_scenario(campaign(seed=9, duration_steps=8, packet_loss_rate=0.35), "auction"))
    second = scientific(run_campaign_scenario(campaign(seed=9, duration_steps=8, packet_loss_rate=0.35), "auction"))
    assert first == second

    outcomes = {
        (
            run_campaign_scenario(campaign(seed=seed, duration_steps=8, packet_loss_rate=0.35), "auction")["metrics"]["messages_dropped"],
            run_campaign_scenario(campaign(seed=seed, duration_steps=8, packet_loss_rate=0.35), "auction")["metrics"]["auction_successes"],
        )
        for seed in range(6)
    }
    assert len(outcomes) > 1


def test_decentralized_context_contains_only_delivered_pair_information():
    runner = CampaignRunner(campaign(duration_steps=2), "greedy")
    runner.world.current_time = 0
    runner._detect_risks()
    before = runner._context("SAT-A")
    assert before.risk_events == ()
    runner._drain_messages([])
    after = runner._context("SAT-A")

    assert not after.global_access
    assert set(after.agent_views) == {"SAT-A"}
    assert set(after.trajectories) == {"SAT-A", "SAT-B"}
    assert "SAT-C" not in after.trajectories


def test_campaign_step_rejects_malformed_and_impersonated_outputs():
    with pytest.raises(TypeError, match="CampaignProtocolStep"):
        check_campaign_step(object(), "SAT-A")
    bad = CampaignProtocolStep(outbound_messages=[
        __import__("src.network.message", fromlist=["Message"]).Message("SAT-B", "SAT-A", MessageType.RISK_ALERT)
    ])
    with pytest.raises(ValueError, match="cannot send"):
        check_campaign_step(bad, "SAT-A")


def test_campaign_metrics_agree_with_trace_counts():
    result = run_campaign_scenario(campaign(duration_steps=8), "auction")

    assert result["metrics"]["bids_received"] == len(events(result, "AUCTION_BID_RECEIVED"))
    assert result["metrics"]["maneuvers_proposed"] == len(events(result, "MANEUVER_PROPOSED"))
    assert result["metrics"]["maneuver_count"] == len(events(result, "MANEUVER_EXECUTED"))


def test_campaign_config_dispatch_artifact_schema_and_viewer(tmp_path):
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    config = load_experiment_config(
        root / "examples" / "campaign.toml",
        overrides={"output.directory": str(tmp_path), "scenario.duration_steps": 7},
    )
    result = run_experiment(config)
    directory, summary = write_run_artifacts(config, result)
    viewed = load_run(directory)

    assert summary["benchmark"] == "spacecraft-campaign-v1"
    assert viewed["artifact_schema_version"] == 3
    assert any(event["event_type"] == "AUCTION_WINNER_SELECTED" for event in viewed["events"])
    assert all(isinstance(value, str) for event in viewed["events"] for value in event["references"].values())


def test_v1_extended_metric_contract_does_not_gain_campaign_fields():
    result = run_closed_loop_scenario(load_scenario("closed_loop_resolved", seed=42), "centralized")
    assert "risks_created" not in result["metrics"]
    assert "auction_successes" not in result["metrics"]


def test_initial_truth_is_paired_across_protocols_for_same_seed():
    results = [run_campaign_scenario(campaign(seed=4, duration_steps=5), name) for name in ("centralized", "greedy", "auction")]
    initial = [
        [event["payload"] for event in result["trace"]["events"] if event["event_type"] == "RISK_CREATED" and event["time"] == 0]
        for result in results
    ]
    assert initial[0] == initial[1] == initial[2]


def test_execution_randomness_does_not_shift_pre_execution_network_faults():
    normal = run_campaign_scenario(campaign(seed=12, duration_steps=5, packet_loss_rate=0.25), "auction")
    failing = run_campaign_scenario(campaign(seed=12, duration_steps=5, packet_loss_rate=0.25, execution_failure_rate=1.0), "auction")

    def attempts(result):
        return [(event["event_type"], event["payload"]["message_id"], event["payload"].get("drop_reason")) for event in result["trace"]["events"] if event["event_type"] in {"MESSAGE_SENT", "MESSAGE_DROPPED"}]
    shared = min(len(attempts(normal)), len(attempts(failing)))
    assert attempts(normal)[:shared] == attempts(failing)[:shared]
