import argparse
import json
import random
import time
from pathlib import Path

from src.agents.satellite_agent import SatelliteAgent
from src.detection.conjunction import detect_conjunctions
from src.metrics.efficiency import estimate_fuel_used
from src.metrics.summary import MetricsSummary
from src.network.faults import NetworkFaultConfig
from src.network.simulator import NetworkSimulator
from src.protocols.centralized import CentralizedProtocol
from src.protocols.greedy import GreedyProtocol
from src.simulation.scenario import ScenarioConfig, load_scenario
from src.simulation.world import WorldState


PROTOCOLS = {
    "centralized": CentralizedProtocol,
    "greedy": GreedyProtocol,
}


def build_agents(config):
    rng = random.Random(config.seed)
    agents = {}

    for index in range(config.agent_count):
        agent_id = f"SAT-{index + 1:03d}"
        agents[agent_id] = SatelliteAgent(
            agent_id=agent_id,
            satellite_name=agent_id,
            fuel_budget=float(rng.randint(50, 100)),
            mission_priority=rng.randint(1, 5),
        )

    return agents


def synthetic_position(agent_id, index, step):
    drift = (step % 3) * 25
    return {
        "satellite": agent_id,
        "time": str(step),
        "x_km": float(index * 900 + drift),
        "y_km": float((index % 2) * 120),
        "z_km": float(step * 10),
    }


def build_position_records(world, step):
    records = []
    for index, agent in enumerate(world.agents.values()):
        position = synthetic_position(agent.agent_id, index, step)
        agent.update_position(position)
        records.append(position)
    return records


def make_protocol(protocol_name):
    if protocol_name not in PROTOCOLS:
        raise ValueError(f"Unknown protocol '{protocol_name}'")
    return PROTOCOLS[protocol_name]()


def run_scenario(config, protocol_name):
    started_at = time.perf_counter()
    network = NetworkSimulator(
        NetworkFaultConfig(
            latency_steps=config.network_latency_steps,
            packet_loss_rate=config.packet_loss_rate,
            bandwidth_limit_per_agent=config.bandwidth_limit_per_agent,
            seed=config.seed,
        )
    )
    world = WorldState(agents=build_agents(config), network=network)
    protocol = make_protocol(protocol_name)
    metrics = MetricsSummary()

    for step in range(config.duration_steps):
        world.current_time = step
        world.reset_agent_plans()
        world.delivered_messages.extend(network.deliver_due(step))

        positions = build_position_records(world, step)
        conjunctions = detect_conjunctions(positions, config.conjunction_threshold_km)
        world.conjunctions.extend(conjunctions)

        decision = protocol.decide(world, conjunctions)
        maneuver_count = len(decision.planned_maneuvers)
        for agent_id in decision.planned_maneuvers:
            world.agents[agent_id].state.fuel_budget -= 1.0

        metrics.conjunctions_detected += len(conjunctions)
        metrics.coordination_attempts += decision.coordination_attempts
        metrics.planned_maneuvers += maneuver_count
        metrics.estimated_fuel_used += estimate_fuel_used(maneuver_count)
        metrics.unresolved_high_risk_conjunctions += decision.unresolved_conjunctions

    final_time = config.duration_steps + config.network_latency_steps
    world.delivered_messages.extend(network.deliver_due(final_time))
    metrics.messages_sent = network.messages_sent
    metrics.messages_delivered = network.messages_delivered
    metrics.messages_dropped = network.messages_dropped
    metrics.runtime_seconds = time.perf_counter() - started_at

    return {
        "protocol": protocol.name,
        "scenario": config.name,
        "agents": config.agent_count,
        "seed": config.seed,
        "metrics": metrics.to_dict(),
    }


def print_summary(result):
    metrics = result["metrics"]
    print(f"Protocol: {result['protocol']}")
    print(f"Agents: {result['agents']}")
    print(f"Seed: {result['seed']}")
    print(f"Conjunctions detected: {metrics['conjunctions_detected']}")
    print(f"Coordination attempts: {metrics['coordination_attempts']}")
    print(f"Maneuvers planned: {metrics['planned_maneuvers']}")
    print(f"Messages sent: {metrics['messages_sent']}")
    print(f"Messages delivered: {metrics['messages_delivered']}")
    print(f"Messages dropped: {metrics['messages_dropped']}")
    print(f"Estimated fuel used: {metrics['estimated_fuel_used']}")
    print(f"Unresolved high-risk conjunctions: {metrics['unresolved_high_risk_conjunctions']}")
    print(f"Runtime seconds: {metrics['runtime_seconds']:.6f}")


def write_json_result(result, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True))


def parse_args():
    parser = argparse.ArgumentParser(description="Run a Themis protocol arena experiment.")
    parser.add_argument("--scenario", default="simple_10")
    parser.add_argument("--protocol", choices=sorted(PROTOCOLS), default="greedy")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-json")
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_scenario(args.scenario, seed=args.seed)
    result = run_scenario(config, args.protocol)
    print_summary(result)

    if args.output_json:
        write_json_result(result, args.output_json)


if __name__ == "__main__":
    main()
