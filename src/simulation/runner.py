import argparse
from copy import deepcopy
import json
import random
import time
from pathlib import Path

from src.agents.satellite_agent import SatelliteAgent
from src.detection.conjunction import detect_conjunctions
from src.metrics.efficiency import estimate_fuel_used
from src.metrics.summary import MetricsSummary
from src.maneuvers.execution import ManeuverExecutor
from src.maneuvers.generator import DeterministicManeuverGenerator
from src.maneuvers.model import ManeuverStatus
from src.maneuvers.validation import ManeuverValidator
from src.network.faults import NetworkFaultConfig
from src.network.message import Message, MessageType
from src.network.simulator import NetworkSimulator
from src.protocols.base import ProtocolContext, make_agent_view
from src.protocols.centralized import CentralizedProtocol
from src.protocols.greedy import GreedyProtocol
from src.risk.events import RiskEvent
from src.risk.reassessment import evaluate_maneuver_outcome
from src.simulation.scenario import ScenarioConfig, load_scenario
from src.simulation.trace import SimulationTrace, format_trace_summary
from src.simulation.world import WorldState
from src.trajectory.linear import LinearTrajectory


PROTOCOLS = {
    "centralized": CentralizedProtocol,
    "greedy": GreedyProtocol,
}


def build_agents(config, random_source=None):
    rng = random_source or random.Random(config.seed)
    agents = {}

    for index in range(config.agent_count):
        if config.initial_states:
            agent_id = config.initial_states[index]["agent_id"]
        else:
            agent_id = f"SAT-{index + 1:03d}"
        agents[agent_id] = SatelliteAgent(
            agent_id=agent_id,
            satellite_name=agent_id,
            fuel_budget=float(config.fuel_budgets.get(agent_id, config.default_fuel_budget if config.initial_states else rng.randint(50, 100))),
            mission_priority=config.mission_priorities.get(agent_id, rng.randint(1, 5)),
        )

    return agents


def build_trajectories(config):
    trajectories = {}
    if config.initial_states:
        for state in config.initial_states:
            trajectories[state["agent_id"]] = LinearTrajectory(
                satellite_id=state["agent_id"],
                reference_time=0,
                position_km=tuple(state["position_km"]),
                velocity_km_per_step=tuple(state["velocity_km_per_step"]),
                trajectory_kind="catalog_reference",
            )
        return trajectories

    for index in range(config.agent_count):
        agent_id = f"SAT-{index + 1:03d}"
        trajectories[agent_id] = LinearTrajectory(
            satellite_id=agent_id,
            reference_time=0,
            position_km=(float(index * 900), float((index % 2) * 120), 0.0),
            velocity_km_per_step=(25.0, 0.0, 10.0),
            trajectory_kind="catalog_reference",
        )
    return trajectories


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


def build_position_records_from_trajectories(trajectories, step):
    return [trajectories[agent_id].position_record_at(step) for agent_id in sorted(trajectories)]


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


def _risk_events_from_conjunctions(conjunctions, config, current_time):
    risk_events = []
    for index, conjunction in enumerate(conjunctions, start=1):
        risk_events.append(
            RiskEvent(
                risk_event_id=f"risk-{current_time}-{index}",
                time=current_time,
                satellite_a=conjunction["satellite_a"],
                satellite_b=conjunction["satellite_b"],
                distance_km=conjunction["distance_km"],
                threshold_km=config.conjunction_threshold_km,
                decision_deadline=current_time + config.decision_deadline_steps,
            )
        )
    return risk_events


def _build_protocol_context(world, protocol, risk_events, generator, config):
    if protocol.name == "centralized":
        agent_views = {agent_id: make_agent_view(agent) for agent_id, agent in world.agents.items()}
        visible_risks = list(risk_events)
        trajectories = deepcopy(world.trajectories)
        global_access = True
    else:
        agent_views = {
            agent_id: make_agent_view(agent)
            for agent_id, agent in world.agents.items()
            if agent.state.known_risk_events
        }
        visible_ids = {
            risk_id
            for view in agent_views.values()
            for risk_id in view.known_risk_events
        }
        visible_risks = [risk for risk in risk_events if risk.risk_event_id in visible_ids]
        trajectories = {
            agent_id: deepcopy(world.trajectories[agent_id])
            for agent_id in agent_views
            if agent_id in world.trajectories
        }
        for risk in visible_risks:
            trajectories[risk.satellite_a] = deepcopy(world.trajectories[risk.satellite_a])
            trajectories[risk.satellite_b] = deepcopy(world.trajectories[risk.satellite_b])
        global_access = False

    return ProtocolContext(
        current_time=world.current_time,
        protocol_name=protocol.name,
        agent_views=agent_views,
        risk_events=visible_risks,
        trajectories=trajectories,
        maneuver_generator=generator,
        reassessment_horizon_steps=config.risk_reassessment_horizon_steps,
        global_access=global_access,
    )


def _send_risk_alerts(world, risk_events):
    for risk_event in risk_events:
        for recipient_id in sorted(risk_event.participants()):
            message = Message(
                sender_id="GROUND_TRUTH_MONITOR",
                recipient_id=recipient_id,
                message_type=MessageType.RISK_ALERT,
                payload={"risk_event": risk_event},
            )
            sent = world.network.send(message, world.current_time)
            event_type = "MESSAGE_SENT" if sent else "MESSAGE_DROPPED"
            world.trace.record(
                world.current_time,
                event_type,
                {
                    "message_type": message.message_type.value,
                    "recipient_id": recipient_id,
                    "risk_event_id": risk_event.risk_event_id,
                },
            )


def _deliver_messages(world, time_step, deadline=None):
    delivered = world.network.deliver_due(time_step)
    for message in delivered:
        world.delivered_messages.append(message)
        if deadline is not None and time_step > deadline:
            event_type = "MESSAGE_DELAYED_BEYOND_USEFULNESS"
        else:
            event_type = "MESSAGE_DELIVERED"
        world.trace.record(
            time_step,
            event_type,
            {
                "message_type": message.message_type.value,
                "sender_id": message.sender_id,
                "recipient_id": message.recipient_id,
            },
        )
        if message.message_type == MessageType.RISK_ALERT and message.recipient_id in world.agents:
            risk_event = message.payload["risk_event"]
            agent = world.agents[message.recipient_id]
            agent.state.known_risk_events[risk_event.risk_event_id] = risk_event
            agent.state.active_conjunctions.add(risk_event.risk_event_id)
            agent.state.risk_state = "HIGH"
            agent.state.last_communication_time = time_step
    return delivered


def _finalize_metrics(metrics, world, outcomes, started_at, config):
    metrics.messages_sent = world.network.messages_sent
    metrics.messages_delivered = world.network.messages_delivered
    metrics.messages_dropped = world.network.messages_dropped
    metrics.messages_delayed_beyond_usefulness = len(
        [event for event in world.trace.events if event.event_type == "MESSAGE_DELAYED_BEYOND_USEFULNESS"]
    )
    metrics.remaining_fuel_by_agent = {
        agent_id: agent.state.fuel_budget for agent_id, agent in sorted(world.agents.items())
    }
    if metrics.resolved_conjunctions:
        metrics.delta_v_per_resolved_conjunction = (
            metrics.total_delta_v_used_km_per_step / metrics.resolved_conjunctions
        )
    metrics.unresolved_high_risk_conjunctions = metrics.unresolved_conjunctions
    metrics.total_simulated_resolution_time_steps = config.duration_steps
    metrics.runtime_seconds = time.perf_counter() - started_at
    if outcomes:
        metrics.minimum_pre_maneuver_separation_km = min(
            outcome["pre_minimum_distance_km"] for outcome in outcomes
        )
        metrics.minimum_post_maneuver_separation_km = min(
            outcome["post_minimum_distance_km"] for outcome in outcomes
        )


def run_closed_loop_scenario(config, protocol_name):
    started_at = time.perf_counter()
    random_source = random.Random(config.seed)
    network = NetworkSimulator(
        NetworkFaultConfig(
            latency_steps=config.network_latency_steps,
            packet_loss_rate=config.packet_loss_rate,
            bandwidth_limit_per_agent=config.bandwidth_limit_per_agent,
            seed=config.seed,
        ),
        random_source=random_source,
    )
    world = WorldState(
        agents=build_agents(config, random_source=random_source),
        network=network,
        trajectories=build_trajectories(config),
    )
    world.original_trajectories = deepcopy(world.trajectories)
    protocol = make_protocol(protocol_name)
    trace = SimulationTrace(
        run_id=f"{config.name}:{protocol.name}:{config.seed}",
        scenario_id=config.name,
        protocol=protocol.name,
        seed=config.seed,
        configuration=config.to_dict(),
    )
    world.trace = trace
    metrics = MetricsSummary()
    generator = DeterministicManeuverGenerator(
        max_delta_v_km_per_step=config.max_delta_v_km_per_step,
        min_delta_v_km_per_step=config.min_delta_v_km_per_step,
    )
    validator = ManeuverValidator()
    executor = ManeuverExecutor(random_source)
    outcomes = []

    world.current_time = 0
    trace.record(0, "STATE_UPDATED", {"trajectories": {key: value.to_dict() for key, value in world.trajectories.items()}})
    positions = build_position_records_from_trajectories(world.trajectories, 0)
    conjunctions = detect_conjunctions(positions, config.conjunction_threshold_km)
    risk_events = _risk_events_from_conjunctions(conjunctions, config, 0)
    metrics.original_conjunctions = len(risk_events)
    metrics.conjunctions_detected = len(risk_events)

    for risk_event in risk_events:
        world.risk_events[risk_event.risk_event_id] = risk_event
        trace.record(0, "CONJUNCTION_DETECTED", risk_event.to_dict())

    _send_risk_alerts(world, risk_events)
    latest_deadline = max((risk.decision_deadline for risk in risk_events), default=0)
    decision_time = min(latest_deadline, config.network_latency_steps)

    for time_step in range(0, decision_time + 1):
        world.current_time = time_step
        _deliver_messages(world, time_step, deadline=latest_deadline)

    world.current_time = decision_time
    context = _build_protocol_context(world, protocol, risk_events, generator, config)
    decision = protocol.propose_maneuvers(context)
    metrics.coordination_attempts += decision.coordination_attempts

    if not decision.maneuver_proposals and risk_events:
        metrics.timeouts += len(risk_events)
        metrics.fallback_activations += len(risk_events)
        trace.record(latest_deadline, "COORDINATION_TIMEOUT", {"risk_event_ids": [risk.risk_event_id for risk in risk_events]})

    seen_proposal_keys = set()
    for proposal in decision.maneuver_proposals:
        world.current_time = proposal.proposal_time
        proposal_key = (proposal.risk_event_id, proposal.agent_id)
        if proposal_key in seen_proposal_keys:
            metrics.duplicate_maneuver_proposals += 1
            proposal.proposal_status = ManeuverStatus.REJECTED.value
            proposal.rejection_reason = "DUPLICATE_PROPOSAL"
        seen_proposal_keys.add(proposal_key)

        metrics.maneuvers_proposed += 1
        metrics.planned_maneuvers += 1
        trace.record(proposal.proposal_time, "MANEUVER_PROPOSED", proposal.to_dict())

        validation = validator.validate(proposal, world, config)
        validator.apply_result_to_proposal(proposal, validation)
        trace.record(proposal.proposal_time, "MANEUVER_VALIDATED" if validation.valid else "MANEUVER_REJECTED", validation.to_dict())

        if not validation.valid:
            metrics.safety_validation_failures += 1
            metrics.unresolved_conjunctions += 1
            world.maneuvers[proposal.maneuver_id] = proposal
            continue

        proposal.proposal_status = ManeuverStatus.ACCEPTED.value
        world.maneuvers[proposal.maneuver_id] = proposal
        agent = world.agents[proposal.agent_id]
        agent.state.accepted_maneuver = proposal.maneuver_id
        agent.state.reserved_fuel += proposal.estimated_fuel_cost
        trace.record(proposal.proposal_time, "MANEUVER_ACCEPTED", {"maneuver_id": proposal.maneuver_id})

        proposal.proposal_status = ManeuverStatus.SCHEDULED.value
        trace.record(proposal.planned_execution_time, "MANEUVER_SCHEDULED", proposal.to_dict())

        pre_trajectories = deepcopy(world.trajectories)
        world.current_time = proposal.planned_execution_time
        execution = executor.execute(proposal, world, config)
        agent.state.reserved_fuel = max(0.0, agent.state.reserved_fuel - proposal.estimated_fuel_cost)
        trace.record(world.current_time, "MANEUVER_EXECUTED" if execution["executed"] else "MANEUVER_FAILED", {**execution, "maneuver": proposal.to_dict()})

        if not execution["executed"]:
            metrics.unresolved_conjunctions += 1
            continue

        metrics.successful_agreements += 1
        metrics.maneuvers_executed += 1
        metrics.estimated_fuel_used += proposal.estimated_fuel_cost
        metrics.total_delta_v_used_km_per_step += proposal.delta_v_magnitude_km_per_step
        metrics.mission_disruption_cost += proposal.expected_mission_disruption_score
        metrics.per_agent_maneuver_burden[proposal.agent_id] = metrics.per_agent_maneuver_burden.get(proposal.agent_id, 0) + 1
        metrics.detection_to_decision_time_steps.append(proposal.proposal_time - world.risk_events[proposal.risk_event_id].time)
        metrics.decision_to_execution_time_steps.append(proposal.planned_execution_time - proposal.proposal_time)
        trace.record(world.current_time, "TRAJECTORY_REPROPAGATED", {"agent_id": proposal.agent_id, "trajectory": world.trajectories[proposal.agent_id].to_dict()})

        outcome = evaluate_maneuver_outcome(
            pre_trajectories,
            world.trajectories,
            world.risk_events[proposal.risk_event_id],
            proposal.agent_id,
            world.current_time + 1,
            config.risk_reassessment_horizon_steps,
        )
        outcomes.append(outcome)
        trace.record(world.current_time, "RISK_REASSESSED", outcome)

        if outcome["outcome"] == "RESOLVED":
            metrics.resolved_conjunctions += 1
            world.risk_events[proposal.risk_event_id].status = "RESOLVED"
            trace.record(world.current_time, "CONJUNCTION_RESOLVED", {"risk_event_id": proposal.risk_event_id})
        elif outcome["outcome"] == "WORSENED":
            metrics.worsened_conjunctions += 1
            metrics.unresolved_conjunctions += 1
        elif outcome["outcome"] == "SECONDARY_RISK_CREATED":
            metrics.secondary_conjunctions_created += len(outcome["secondary_conjunctions"])
            metrics.unresolved_conjunctions += 1
            trace.record(world.current_time, "SECONDARY_CONJUNCTION_DETECTED", {"findings": outcome["secondary_conjunctions"]})
        else:
            metrics.unresolved_conjunctions += 1

    unresolved_open = len([risk for risk in world.risk_events.values() if risk.status == "OPEN"])
    if not decision.maneuver_proposals:
        metrics.unresolved_conjunctions = max(metrics.unresolved_conjunctions, unresolved_open)
    final_delivery_time = config.duration_steps + config.network_latency_steps
    world.current_time = final_delivery_time
    _deliver_messages(world, final_delivery_time, deadline=latest_deadline)
    _finalize_metrics(metrics, world, outcomes, started_at, config)

    result = {
        "run_id": trace.run_id,
        "protocol": protocol.name,
        "scenario": config.name,
        "agents": config.agent_count,
        "seed": config.seed,
        "configuration": config.to_dict(),
        "initial_risk_events": [risk.to_dict() for risk in risk_events],
        "maneuver_proposals": [maneuver.to_dict() for maneuver in world.maneuvers.values()],
        "risk_outcomes": outcomes,
        "metrics": metrics.to_dict(include_extended=True),
        "trace": trace.to_dict(),
    }
    trace.record(config.duration_steps, "RUN_COMPLETED", {"metrics": metrics.to_dict(include_extended=True)})
    result["trace"] = trace.to_dict()
    return result


def print_summary(result):
    metrics = result["metrics"]
    print(f"Scenario: {result['scenario']}")
    print(f"Protocol: {result['protocol']}")
    print(f"Agents: {result['agents']}")
    print(f"Seed: {result['seed']}")
    print(f"Initial conjunctions: {metrics.get('original_conjunctions', metrics['conjunctions_detected'])}")
    print(f"Conjunctions detected: {metrics['conjunctions_detected']}")
    print(f"Coordination attempts: {metrics['coordination_attempts']}")
    print(f"Maneuvers proposed: {metrics.get('maneuvers_proposed', metrics['planned_maneuvers'])}")
    print(f"Maneuvers planned: {metrics['planned_maneuvers']}")
    print(f"Maneuvers executed: {metrics.get('maneuvers_executed', 0)}")
    print(f"Resolved conjunctions: {metrics.get('resolved_conjunctions', 0)}")
    print(f"Unresolved conjunctions: {metrics.get('unresolved_conjunctions', metrics['unresolved_high_risk_conjunctions'])}")
    print(f"Secondary conjunctions: {metrics.get('secondary_conjunctions_created', 0)}")
    print(f"Total delta-v used: {metrics.get('total_delta_v_used_km_per_step', 0.0)} km/step")
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
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run a closed-loop scenario.")
    run_parser.add_argument("--scenario", default="closed_loop_resolved")
    run_parser.add_argument("--protocol", choices=sorted(PROTOCOLS), default="greedy")
    run_parser.add_argument("--seed", type=int, default=42)
    run_parser.add_argument("--output", "--output-json", dest="output_json")

    replay_parser = subparsers.add_parser("replay", help="Inspect a saved run trace.")
    replay_parser.add_argument("path")

    parser.add_argument("--scenario", default="simple_10")
    parser.add_argument("--protocol", choices=sorted(PROTOCOLS), default="greedy")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-json")
    return parser.parse_args()


def load_result(path):
    return json.loads(Path(path).read_text())


def main():
    args = parse_args()

    if args.command == "replay":
        result = load_result(args.path)
        print(format_trace_summary(result["trace"]))
        return

    if args.command == "run":
        config = load_scenario(args.scenario, seed=args.seed)
        result = run_closed_loop_scenario(config, args.protocol)
        print_summary(result)
        if args.output_json:
            write_json_result(result, args.output_json)
            print(f"Trace output path: {args.output_json}")
        return

    config = load_scenario(args.scenario, seed=args.seed)
    result = run_scenario(config, args.protocol)
    print_summary(result)

    if args.output_json:
        write_json_result(result, args.output_json)


if __name__ == "__main__":
    main()
