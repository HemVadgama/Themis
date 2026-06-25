from src.agents.satellite_agent import SatelliteAgent
from src.network.faults import NetworkFaultConfig
from src.network.simulator import NetworkSimulator
from src.protocols.centralized import CentralizedProtocol
from src.protocols.greedy import GreedyProtocol
from src.simulation.world import WorldState


def make_world():
    agents = {
        "SAT-A": SatelliteAgent("SAT-A", "SAT-A", fuel_budget=10.0, mission_priority=1),
        "SAT-B": SatelliteAgent("SAT-B", "SAT-B", fuel_budget=50.0, mission_priority=5),
    }
    network = NetworkSimulator(NetworkFaultConfig(packet_loss_rate=0.0, seed=1))
    return WorldState(agents=agents, network=network)


def test_centralized_protocol_selects_lower_priority_agent():
    world = make_world()
    conjunctions = [
        {
            "time": "0",
            "satellite_a": "SAT-A",
            "satellite_b": "SAT-B",
            "distance_km": 500.0,
        }
    ]

    decision = CentralizedProtocol().decide(world, conjunctions)

    assert decision.coordination_attempts == 1
    assert decision.planned_maneuvers == ["SAT-A"]
    assert world.agents["SAT-A"].state.planned_action == "MANEUVER"
    assert world.agents["SAT-B"].state.planned_action == "NONE"


def test_greedy_protocol_uses_local_risk_to_plan_maneuvers():
    world = make_world()
    conjunctions = [
        {
            "time": "0",
            "satellite_a": "SAT-A",
            "satellite_b": "SAT-B",
            "distance_km": 500.0,
        }
    ]

    decision = GreedyProtocol().decide(world, conjunctions)

    assert decision.coordination_attempts == 1
    assert set(decision.planned_maneuvers) == {"SAT-A", "SAT-B"}
    assert world.agents["SAT-A"].state.risk_state == "HIGH"
    assert world.agents["SAT-B"].state.risk_state == "HIGH"
    assert world.network.messages_sent == 2
