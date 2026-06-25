from src.simulation.clock import SimulationClock
from src.simulation.runner import run_scenario
from src.simulation.scenario import ScenarioConfig


def comparable_result(result):
    comparable = dict(result)
    comparable["metrics"] = dict(result["metrics"])
    comparable["metrics"].pop("runtime_seconds")
    return comparable


def test_simulation_clock_orders_by_time_priority_and_sequence():
    clock = SimulationClock()
    clock.schedule(2, "later")
    clock.schedule(1, "same_time_second", priority=1)
    clock.schedule(1, "same_time_first", priority=0)

    assert clock.pop_next().event_type == "same_time_first"
    assert clock.pop_next().event_type == "same_time_second"
    assert clock.pop_next().event_type == "later"


def test_simulation_runs_are_deterministic_for_same_seed():
    config = ScenarioConfig(
        name="test",
        agent_count=4,
        duration_steps=3,
        conjunction_threshold_km=1000.0,
        seed=42,
        network_latency_steps=0,
        packet_loss_rate=0.0,
        bandwidth_limit_per_agent=10,
    )

    first = run_scenario(config, "greedy")
    second = run_scenario(config, "greedy")

    assert comparable_result(first) == comparable_result(second)
