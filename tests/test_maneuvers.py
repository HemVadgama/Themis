from copy import deepcopy
import random

from src.agents.satellite_agent import SatelliteAgent
from src.maneuvers.execution import ManeuverExecutor
from src.maneuvers.generator import DeterministicManeuverGenerator
from src.maneuvers.model import ManeuverStatus
from src.maneuvers.validation import ManeuverValidator
from src.network.faults import NetworkFaultConfig
from src.network.simulator import NetworkSimulator
from src.risk.events import RiskEvent
from src.simulation.scenario import load_scenario
from src.simulation.world import WorldState
from src.trajectory.linear import LinearTrajectory


def make_world(fuel_budget=200.0):
    agents = {
        "SAT-A": SatelliteAgent("SAT-A", "SAT-A", fuel_budget=fuel_budget, mission_priority=1),
        "SAT-B": SatelliteAgent("SAT-B", "SAT-B", fuel_budget=200.0, mission_priority=5),
    }
    trajectories = {
        "SAT-A": LinearTrajectory("SAT-A", 0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        "SAT-B": LinearTrajectory("SAT-B", 0, (30.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
    }
    risk_event = RiskEvent("risk-1", 0, "SAT-A", "SAT-B", 30.0, 50.0, 2)
    return WorldState(
        agents=agents,
        network=NetworkSimulator(NetworkFaultConfig()),
        trajectories=trajectories,
        risk_events={risk_event.risk_event_id: risk_event},
    ), risk_event


def test_maneuver_candidate_generation_improves_projected_separation():
    world, risk_event = make_world()
    generator = DeterministicManeuverGenerator(min_delta_v_km_per_step=20.0, max_delta_v_km_per_step=80.0)

    proposal = generator.best_candidate(
        "SAT-A",
        risk_event,
        world.trajectories,
        current_time=0,
        protocol_name="centralized",
        horizon_steps=3,
    )

    assert proposal is not None
    assert proposal.proposal_status == ManeuverStatus.PROPOSED.value
    assert proposal.expected_post_maneuver_separation_km > risk_event.distance_km
    assert proposal.delta_v_magnitude_km_per_step == 80.0


def test_validation_rejects_insufficient_fuel():
    world, risk_event = make_world(fuel_budget=5.0)
    config = load_scenario("closed_loop_resolved", seed=1)
    proposal = DeterministicManeuverGenerator(80.0, 20.0).best_candidate(
        "SAT-A", risk_event, world.trajectories, 0, "centralized", 3
    )

    result = ManeuverValidator().validate(proposal, world, config)

    assert not result.valid
    assert result.reason_code == "INSUFFICIENT_FUEL"


def test_validation_rejects_stale_proposal_after_deadline():
    world, risk_event = make_world()
    config = load_scenario("closed_loop_resolved", seed=1)
    world.current_time = 3
    proposal = DeterministicManeuverGenerator(80.0, 20.0).best_candidate(
        "SAT-A", risk_event, world.trajectories, 3, "centralized", 3
    )

    result = ManeuverValidator().validate(proposal, world, config)

    assert not result.valid
    assert result.reason_code == "MISSED_DEADLINE"


def test_execution_updates_trajectory_and_accounts_fuel_once():
    world, risk_event = make_world()
    config = load_scenario("closed_loop_resolved", seed=1)
    proposal = DeterministicManeuverGenerator(80.0, 20.0).best_candidate(
        "SAT-A", risk_event, world.trajectories, 0, "centralized", 3
    )
    validation = ManeuverValidator().validate(proposal, world, config)
    assert validation.valid

    world.current_time = proposal.planned_execution_time
    executor = ManeuverExecutor(random.Random(1))
    first = executor.execute(proposal, world, config)
    second = executor.execute(proposal, world, config)

    assert first["executed"]
    assert not second["executed"]
    assert second["reason_code"] == "DUPLICATE_EXECUTION"
    assert world.agents["SAT-A"].state.fuel_budget == 120.0
    assert world.trajectories["SAT-A"].trajectory_kind == "post_maneuver"
    assert proposal.execution_status == ManeuverStatus.EXECUTED.value


def test_original_trajectory_copy_is_not_mutated_by_execution():
    world, risk_event = make_world()
    original = deepcopy(world.trajectories)
    config = load_scenario("closed_loop_resolved", seed=1)
    proposal = DeterministicManeuverGenerator(80.0, 20.0).best_candidate(
        "SAT-A", risk_event, world.trajectories, 0, "centralized", 3
    )

    world.current_time = proposal.planned_execution_time
    ManeuverExecutor(random.Random(1)).execute(proposal, world, config)

    assert original["SAT-A"].velocity_km_per_step == (0.0, 0.0, 0.0)
    assert world.trajectories["SAT-A"].velocity_km_per_step != original["SAT-A"].velocity_km_per_step
