"""Deterministic multi-cycle runner for ``spacecraft-campaign-v1``."""

from copy import deepcopy
import hashlib
import random
import time

from src.detection.conjunction import detect_conjunctions
from src.metrics.summary import MetricsSummary
from src.maneuvers.execution import ManeuverExecutor
from src.maneuvers.generator import DeterministicManeuverGenerator
from src.maneuvers.model import ManeuverStatus
from src.maneuvers.validation import ManeuverValidator
from src.network.faults import NetworkFaultConfig
from src.network.message import Message, MessageType
from src.network.simulator import NetworkSimulator
from src.protocols.base import CampaignProtocolContext, make_agent_view
from src.protocols.campaign import COORDINATOR_ID, check_campaign_step, make_campaign_protocol
from src.protocols.registry import make_protocol
from src.risk.events import RiskEvent
from src.risk.reassessment import evaluate_maneuver_outcome
from src.simulation.runner import _agent_snapshot, build_agents, build_position_records_from_trajectories, build_trajectories
from src.simulation.trace import SimulationTrace
from src.simulation.world import WorldState
from src.trajectory.linear import LinearTrajectory


def _stream_seed(seed, label):
    digest = hashlib.sha256(f"spacecraft-campaign-v1:{seed}:{label}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _trajectory_from_dict(value):
    return LinearTrajectory(
        satellite_id=value["satellite_id"],
        reference_time=value["reference_time"],
        position_km=tuple(value["position_km"]),
        velocity_km_per_step=tuple(value["velocity_km_per_step"]),
        trajectory_kind=value.get("trajectory_kind", "belief_snapshot"),
    )


def _risk_from_dict(value):
    return RiskEvent(**deepcopy(value))


def _gini(values):
    ordered = sorted(float(value) for value in values)
    if not ordered or sum(ordered) == 0:
        return 0.0
    n = len(ordered)
    return sum((2 * index - n - 1) * value for index, value in enumerate(ordered, start=1)) / (n * sum(ordered))


class CampaignRunner:
    """Own campaign truth and execute a run-scoped protocol through messages."""

    def __init__(self, config, protocol_name):
        self.config = config
        self.protocol_name = protocol_name
        self.started_at = time.perf_counter()
        scenario_rng = random.Random(_stream_seed(config.seed, "scenario"))
        network_rng = random.Random(_stream_seed(config.seed, "network"))
        execution_rng = random.Random(_stream_seed(config.seed, "execution"))
        network = NetworkSimulator(
            NetworkFaultConfig(config.network_latency_steps, config.packet_loss_rate, config.bandwidth_limit_per_agent, _stream_seed(config.seed, "network")),
            random_source=network_rng,
        )
        self.world = WorldState(
            agents=build_agents(config, random_source=scenario_rng),
            network=network,
            trajectories=build_trajectories(config),
        )
        self.world.original_trajectories = deepcopy(self.world.trajectories)
        self.protocol = make_campaign_protocol(make_protocol(protocol_name))
        self.actors = tuple(self.protocol.actors(tuple(sorted(self.world.agents))))
        self.beliefs = {actor: {"risks": {}, "trajectories": {}} for actor in self.actors}
        self.trace = SimulationTrace(
            f"{config.name}:{protocol_name}:{config.seed}", config.name, protocol_name, config.seed, config.to_dict(), schema_version=3
        )
        self.world.trace = self.trace
        self.metrics = MetricsSummary()
        self.generator = DeterministicManeuverGenerator(config.max_delta_v_km_per_step, config.min_delta_v_km_per_step)
        self.validator = ManeuverValidator()
        self.executor = ManeuverExecutor(execution_rng)
        self.active_by_pair = {}
        self.pair_generations = {}
        self.scheduled = {}
        self.last_maneuver_by_agent = {}
        self.outcomes = []

    @property
    def auction_weights(self):
        return {
            "maneuver_cost": self.config.auction_maneuver_cost_weight,
            "mission_priority": self.config.auction_mission_priority_weight,
            "fuel_scarcity": self.config.auction_fuel_scarcity_weight,
            "risk_reduction": self.config.auction_risk_reduction_weight,
            "deadline_slack": self.config.auction_deadline_slack_weight,
        }

    def _record_message_attempt(self, message, sent):
        payload = message.payload if isinstance(message.payload, dict) else {}
        references = {"message_id": message.message_id}
        for key in ("risk_event_id", "auction_id", "bid_id", "award_id"):
            if payload.get(key):
                references[key] = str(payload[key])
        self.trace.record(
            self.world.current_time,
            "MESSAGE_SENT" if sent else "MESSAGE_DROPPED",
            {
                "message_id": message.message_id,
                "message_type": message.message_type.value,
                "sender_id": message.sender_id,
                "recipient_id": message.recipient_id,
                "sent_time": message.sent_time,
                "deliver_at": message.deliver_at,
                "drop_reason": message.drop_reason,
            },
            actor=message.sender_id,
            entity_ids=[message.recipient_id],
            references=references,
        )

    def _send(self, message):
        sent = self.world.network.send(message, self.world.current_time)
        self._record_message_attempt(message, sent)
        return sent

    def _send_risk_alert(self, risk):
        snapshots = {
            agent_id: self.world.trajectories[agent_id].to_dict()
            for agent_id in sorted(risk.participants())
        }
        payload = {
            "risk_event_id": risk.risk_event_id,
            "risk_event": risk.to_dict(include_campaign=True),
            "trajectory_snapshots": snapshots,
            "deadline": risk.decision_deadline,
        }
        if self.protocol_name == "centralized":
            recipients = [COORDINATOR_ID]
        elif self.protocol_name == "auction":
            recipients = [min(risk.participants())]
        else:
            recipients = sorted(risk.participants())
        for recipient in recipients:
            self._send(Message("GROUND_TRUTH_MONITOR", recipient, MessageType.RISK_ALERT, deepcopy(payload)))

    def _update_belief(self, message, time_step):
        belief = self.beliefs.get(message.recipient_id)
        if belief is None or not isinstance(message.payload, dict):
            return
        risk_value = message.payload.get("risk_event")
        if isinstance(risk_value, dict) and "risk_event_id" in risk_value:
            risk = _risk_from_dict(risk_value)
            belief["risks"][risk.risk_event_id] = risk
            if message.recipient_id in self.world.agents:
                agent = self.world.agents[message.recipient_id]
                before = _agent_snapshot(agent)
                agent.state.known_risk_events[risk.risk_event_id] = deepcopy(risk)
                agent.state.active_conjunctions.add(risk.risk_event_id)
                agent.state.risk_state = "HIGH"
                agent.state.last_communication_time = time_step
                self.trace.record(time_step, "AGENT_STATE_UPDATED", {"trigger": message.message_type.value, "before": before, "after": _agent_snapshot(agent)}, actor=agent.agent_id, entity_ids=[agent.agent_id], references={"message_id": message.message_id, "risk_event_id": risk.risk_event_id})
        for agent_id, trajectory in message.payload.get("trajectory_snapshots", {}).items():
            belief["trajectories"][agent_id] = _trajectory_from_dict(trajectory)

    def _is_late(self, message, time_step):
        payload = message.payload if isinstance(message.payload, dict) else {}
        if message.message_type == MessageType.AUCTION_BID:
            return time_step > payload.get("collection_deadline", time_step)
        if message.message_type == MessageType.AUCTION_ANNOUNCEMENT:
            return time_step + self.config.network_latency_steps > payload.get("collection_deadline", time_step)
        if message.message_type in {MessageType.AUCTION_AWARD, MessageType.MANEUVER_DIRECTIVE, MessageType.RISK_ALERT}:
            return time_step + 1 > payload.get("deadline", time_step + 1)
        return time_step > payload.get("deadline", time_step)

    def _context(self, actor):
        belief = self.beliefs[actor]
        if actor == COORDINATOR_ID:
            views = {agent_id: make_agent_view(agent) for agent_id, agent in sorted(self.world.agents.items())}
            trajectories = deepcopy(self.world.trajectories)
            agent_view = None
            global_access = True
        else:
            agent_view = make_agent_view(self.world.agents[actor])
            views = {actor: agent_view}
            trajectories = deepcopy(belief["trajectories"])
            global_access = False
        return CampaignProtocolContext(
            actor, self.world.current_time, self.protocol_name, agent_view, views,
            tuple(deepcopy(belief["risks"][key]) for key in sorted(belief["risks"])),
            trajectories, self.generator, self.config.risk_reassessment_horizon_steps,
            self.config.network_latency_steps, self.auction_weights, global_access,
        )

    def _record_transition(self, actor, transition):
        self.trace.record(
            self.world.current_time,
            transition["event_type"],
            transition.get("payload", {}),
            actor=actor,
            entity_ids=transition.get("entity_ids", []),
            references={key: str(value) for key, value in transition.get("references", {}).items()},
        )

    def _handle_step(self, actor, step, pending_proposals):
        step = check_campaign_step(step, actor)
        for transition in step.trace_transitions:
            self._record_transition(actor, transition)
        for message in step.outbound_messages:
            self._send(message)
        pending_proposals.extend(step.maneuver_proposals)

    def _drain_messages(self, pending_proposals, *, allow_protocol=True):
        iterations = 0
        while True:
            delivered = self.world.network.deliver_due(self.world.current_time)
            if not delivered:
                break
            iterations += 1
            if iterations > 10000:
                raise RuntimeError("Campaign protocol did not quiesce at one timestamp.")
            for message in delivered:
                self.world.delivered_messages.append(message)
                late = self._is_late(message, self.world.current_time)
                references = {"message_id": message.message_id}
                payload = message.payload if isinstance(message.payload, dict) else {}
                for key in ("risk_event_id", "auction_id", "bid_id", "award_id"):
                    if payload.get(key):
                        references[key] = str(payload[key])
                self.trace.record(
                    self.world.current_time,
                    "MESSAGE_DELAYED_BEYOND_USEFULNESS" if late else "MESSAGE_DELIVERED",
                    {"message_id": message.message_id, "message_type": message.message_type.value, "sender_id": message.sender_id, "recipient_id": message.recipient_id, "sent_time": message.sent_time, "delivered_time": self.world.current_time, "latency_steps": self.world.current_time - message.sent_time, "late": late},
                    actor=message.sender_id,
                    entity_ids=[message.recipient_id],
                    references=references,
                )
                self._update_belief(message, self.world.current_time)
                if allow_protocol and not late and message.recipient_id in self.beliefs:
                    step = self.protocol.on_message(message, self._context(message.recipient_id))
                    self._handle_step(message.recipient_id, step, pending_proposals)

    def _detect_risks(self):
        positions = build_position_records_from_trajectories(self.world.trajectories, self.world.current_time)
        conjunctions = detect_conjunctions(positions, self.config.conjunction_threshold_km)
        current_pairs = {tuple(sorted((item["satellite_a"], item["satellite_b"]))): item for item in conjunctions}
        for pair, risk_id in sorted(list(self.active_by_pair.items())):
            if pair in current_pairs:
                continue
            risk = self.world.risk_events[risk_id]
            if risk_id in self.world.risk_commitments:
                continue
            if risk.status == "OPEN" and risk.metadata.get("executed_maneuver_id"):
                risk.status = "RESOLVED"
                risk.resolution_time = self.world.current_time
                self.metrics.risks_resolved += 1
                self.metrics.resolved_conjunctions += 1
                self.metrics.risk_resolution_time_steps.append(self.world.current_time - risk.time)
            elif risk.status == "OPEN":
                risk.status = "CLOSED"
                self.metrics.risks_closed += 1
            risk.closed_time = self.world.current_time
            self.trace.record(self.world.current_time, "RISK_CLOSED", {"risk_event": risk.to_dict(include_campaign=True), "reason": "separation_above_threshold"}, actor="risk-monitor", entity_ids=list(pair), references={"risk_event_id": risk_id})
            self.active_by_pair.pop(pair)
            for agent_id in pair:
                self.world.agents[agent_id].state.active_conjunctions.discard(risk_id)

        for pair, conjunction in sorted(current_pairs.items()):
            if pair in self.active_by_pair:
                risk = self.world.risk_events[self.active_by_pair[pair]]
                risk.distance_km = conjunction["distance_km"]
                risk.updated_time = self.world.current_time
                self.trace.record(self.world.current_time, "RISK_UPDATED", {"risk_event": risk.to_dict(include_campaign=True), "transition": "CONTINUING"}, actor="risk-monitor", entity_ids=list(pair), references={"risk_event_id": risk.risk_event_id})
                continue
            generation = self.pair_generations.get(pair, 0) + 1
            self.pair_generations[pair] = generation
            risk_id = f"risk:{pair[0]}:{pair[1]}:{generation:03d}"
            causal = max((self.last_maneuver_by_agent.get(agent_id) for agent_id in pair if self.last_maneuver_by_agent.get(agent_id)), default=None)
            classification = "SECONDARY" if causal else "PRIMARY"
            risk = RiskEvent(
                risk_id, self.world.current_time, pair[0], pair[1], conjunction["distance_km"],
                self.config.conjunction_threshold_km, self.world.current_time + self.config.decision_deadline_steps,
                classification=classification, updated_time=self.world.current_time, causal_maneuver_id=causal,
            )
            self.world.risk_events[risk_id] = risk
            self.active_by_pair[pair] = risk_id
            self.metrics.risks_created += 1
            self.metrics.conjunctions_detected += 1
            if classification == "PRIMARY":
                self.metrics.primary_risks_created += 1
                if self.world.current_time == 0:
                    self.metrics.original_conjunctions += 1
            else:
                self.metrics.secondary_risks_created += 1
                self.metrics.secondary_conjunctions_created += 1
            self.trace.record(self.world.current_time, "RISK_CREATED", {"risk_event": risk.to_dict(include_campaign=True), "transition": "NEW"}, actor="risk-monitor", entity_ids=list(pair), references={key: value for key, value in {"risk_event_id": risk_id, "maneuver_id": causal}.items() if value})
            self._send_risk_alert(risk)
        open_count = sum(risk.status == "OPEN" for risk in self.world.risk_events.values())
        self.metrics.peak_concurrent_open_risks = max(self.metrics.peak_concurrent_open_risks, open_count)

    def _validate_proposals(self, proposals):
        for proposal in sorted(proposals, key=lambda value: (value.proposal_time, value.risk_event_id, value.agent_id, value.maneuver_id)):
            self.metrics.maneuvers_proposed += 1
            self.metrics.planned_maneuvers += 1
            self.trace.record(self.world.current_time, "MANEUVER_PROPOSED", proposal.to_dict(), actor=proposal.agent_id, entity_ids=[proposal.agent_id], references={**{"maneuver_id": proposal.maneuver_id, "risk_event_id": proposal.risk_event_id}, **{key: str(value) for key, value in proposal.metadata.items() if key in {"auction_id", "bid_id", "award_id"}}})
            validation = self.validator.validate(proposal, self.world, self.config)
            self.validator.apply_result_to_proposal(proposal, validation)
            event_type = "MANEUVER_VALIDATED" if validation.valid else "MANEUVER_REJECTED"
            self.trace.record(self.world.current_time, event_type, {**validation.to_dict(), "maneuver_id": proposal.maneuver_id, "risk_event_id": proposal.risk_event_id, "agent_id": proposal.agent_id}, actor="safety-validator", entity_ids=[proposal.agent_id], references={"maneuver_id": proposal.maneuver_id, "risk_event_id": proposal.risk_event_id})
            self.world.maneuvers[proposal.maneuver_id] = proposal
            if not validation.valid:
                self.metrics.maneuvers_rejected += 1
                self.metrics.proposals_rejected += 1
                self.metrics.safety_validation_failures += 1
                if validation.reason_code in {"INSUFFICIENT_FUEL", "INSUFFICIENT_FUEL_AT_EXECUTION"}:
                    self.metrics.resource_exhaustion_events += 1
                continue
            proposal.proposal_status = ManeuverStatus.ACCEPTED.value
            agent = self.world.agents[proposal.agent_id]
            agent.state.accepted_maneuver = proposal.maneuver_id
            agent.state.reserved_fuel += proposal.estimated_fuel_cost
            self.world.risk_commitments[proposal.risk_event_id] = proposal.maneuver_id
            self.scheduled[proposal.maneuver_id] = proposal
            self.metrics.proposals_accepted += 1
            risk = self.world.risk_events[proposal.risk_event_id]
            if proposal.proposal_time <= risk.decision_deadline:
                self.metrics.decisions_completed_before_deadline += 1
            self.trace.record(self.world.current_time, "MANEUVER_ACCEPTED", {"maneuver_id": proposal.maneuver_id, "risk_event_id": proposal.risk_event_id, "agent_id": proposal.agent_id, "planned_execution_time": proposal.planned_execution_time}, actor="safety-validator", entity_ids=[proposal.agent_id], references={"maneuver_id": proposal.maneuver_id, "risk_event_id": proposal.risk_event_id})
            proposal.proposal_status = ManeuverStatus.SCHEDULED.value
            self.trace.record(self.world.current_time, "MANEUVER_SCHEDULED", proposal.to_dict(), actor=proposal.agent_id, entity_ids=[proposal.agent_id], references={"maneuver_id": proposal.maneuver_id, "risk_event_id": proposal.risk_event_id})

    def _execute_due(self):
        due = [proposal for proposal in self.scheduled.values() if proposal.planned_execution_time <= self.world.current_time]
        for proposal in sorted(due, key=lambda value: (value.planned_execution_time, value.risk_event_id, value.agent_id)):
            self.scheduled.pop(proposal.maneuver_id, None)
            agent = self.world.agents[proposal.agent_id]
            before_agent = _agent_snapshot(agent)
            fuel_before = agent.state.fuel_budget
            reserved_before = agent.state.reserved_fuel
            pre_trajectories = deepcopy(self.world.trajectories)
            execution = self.executor.execute(proposal, self.world, self.config)
            agent.state.reserved_fuel = max(0.0, agent.state.reserved_fuel - proposal.estimated_fuel_cost)
            if not execution["executed"]:
                agent.state.accepted_maneuver = None
                self.world.risk_commitments.pop(proposal.risk_event_id, None)
            self.trace.record(self.world.current_time, "MANEUVER_EXECUTED" if execution["executed"] else "MANEUVER_FAILED", {**execution, "maneuver": proposal.to_dict()}, actor=proposal.agent_id, entity_ids=[proposal.agent_id], references={"maneuver_id": proposal.maneuver_id, "risk_event_id": proposal.risk_event_id})
            self.trace.record(self.world.current_time, "AGENT_STATE_UPDATED", {"trigger": "MANEUVER_EXECUTED" if execution["executed"] else "MANEUVER_FAILED", "before": before_agent, "after": _agent_snapshot(agent)}, actor=proposal.agent_id, entity_ids=[proposal.agent_id], references={"maneuver_id": proposal.maneuver_id, "risk_event_id": proposal.risk_event_id})
            self.trace.record(self.world.current_time, "RESOURCE_UPDATED", {"agent_id": proposal.agent_id, "resource": "maneuver_resource_proxy", "before": fuel_before, "after": agent.state.fuel_budget, "reserved_before": reserved_before, "reserved_after": agent.state.reserved_fuel, "change": agent.state.fuel_budget - fuel_before}, actor=proposal.agent_id, entity_ids=[proposal.agent_id], references={"maneuver_id": proposal.maneuver_id, "risk_event_id": proposal.risk_event_id})
            if not execution["executed"]:
                self.metrics.maneuvers_failed += 1
                self.metrics.execution_failures += 1
                continue
            self.world.risk_commitments.pop(proposal.risk_event_id, None)
            self.metrics.maneuvers_executed += 1
            self.metrics.maneuver_count += 1
            self.metrics.successful_agreements += 1
            self.metrics.estimated_fuel_used += proposal.estimated_fuel_cost
            self.metrics.modeled_maneuver_cost += proposal.estimated_fuel_cost
            self.metrics.total_delta_v_used_km_per_step += proposal.delta_v_magnitude_km_per_step
            self.metrics.per_agent_maneuver_burden[proposal.agent_id] = self.metrics.per_agent_maneuver_burden.get(proposal.agent_id, 0) + 1
            self.metrics.per_agent_resource_consumption[proposal.agent_id] = self.metrics.per_agent_resource_consumption.get(proposal.agent_id, 0.0) + proposal.estimated_fuel_cost
            self.last_maneuver_by_agent[proposal.agent_id] = proposal.maneuver_id
            risk = self.world.risk_events[proposal.risk_event_id]
            risk.metadata["executed_maneuver_id"] = proposal.maneuver_id
            outcome = evaluate_maneuver_outcome(pre_trajectories, self.world.trajectories, risk, proposal.agent_id, self.world.current_time + 1, self.config.risk_reassessment_horizon_steps)
            self.outcomes.append(outcome)
            self.trace.record(self.world.current_time, "RISK_REASSESSED", outcome, actor="risk-monitor", entity_ids=sorted(risk.participants()), references={"maneuver_id": proposal.maneuver_id, "risk_event_id": risk.risk_event_id})
            if outcome["post_minimum_distance_km"] > risk.threshold_km:
                risk.status = "RESOLVED"
                risk.resolution_time = self.world.current_time
                self.metrics.risks_resolved += 1
                self.metrics.resolved_conjunctions += 1
                self.metrics.risk_resolution_time_steps.append(self.world.current_time - risk.time)
                self.trace.record(self.world.current_time, "CONJUNCTION_RESOLVED", {"risk_event_id": risk.risk_event_id, "resolution_basis": "modeled_reassessment_horizon"}, actor="risk-monitor", entity_ids=sorted(risk.participants()), references={"maneuver_id": proposal.maneuver_id, "risk_event_id": risk.risk_event_id})

    def _expire_deadlines(self):
        for risk in sorted(self.world.risk_events.values(), key=lambda item: item.risk_event_id):
            if risk.status == "OPEN" and self.world.current_time >= risk.decision_deadline and risk.risk_event_id not in self.world.risk_commitments:
                risk.status = "EXPIRED"
                self.metrics.risks_expired += 1
                self.metrics.decision_deadline_misses += 1
                self.metrics.timeouts += 1
                self.trace.record(self.world.current_time, "RISK_EXPIRED", {"risk_event": risk.to_dict(include_campaign=True), "reason": "no_accepted_action_by_deadline"}, actor="risk-monitor", entity_ids=sorted(risk.participants()), references={"risk_event_id": risk.risk_event_id})

    def _snapshot(self):
        self.trace.record(
            self.world.current_time,
            "STATE_SNAPSHOT",
            {
                "truth": {
                    "trajectories": {key: value.to_dict() for key, value in sorted(self.world.trajectories.items())},
                    "risks": {key: value.to_dict(include_campaign=True) for key, value in sorted(self.world.risk_events.items())},
                    "resources": {key: {"remaining": agent.state.fuel_budget, "reserved": agent.state.reserved_fuel} for key, agent in sorted(self.world.agents.items())},
                },
                "beliefs": {actor: {"known_risk_event_ids": sorted(value["risks"]), "known_trajectory_ids": sorted(value["trajectories"])} for actor, value in sorted(self.beliefs.items())},
            },
            actor="simulation",
            entity_ids=sorted(self.world.agents),
        )

    def run(self):
        self.trace.record(0, "RUN_STARTED", {"scenario": self.config.name, "protocol": self.protocol_name, "seed": self.config.seed, "benchmark": "spacecraft-campaign-v1", "random_streams": ["scenario", "network", "execution"], "event_order": ["propagate", "detect_and_transition_risks", "deliver_and_update_beliefs", "protocol_timers", "validate", "execute", "expire", "snapshot"]}, actor="simulation", entity_ids=sorted(self.world.agents))
        for time_step in range(self.config.duration_steps):
            self.world.current_time = time_step
            pending_proposals = []
            self.trace.record(time_step, "CYCLE_STARTED", {"cycle": time_step}, actor="simulation", entity_ids=sorted(self.world.agents))
            self.trace.record(time_step, "STATE_UPDATED", {"phase": "propagated", "positions": build_position_records_from_trajectories(self.world.trajectories, time_step)}, actor="simulation", entity_ids=sorted(self.world.agents))
            self._detect_risks()
            self._drain_messages(pending_proposals)
            for actor in self.actors:
                self._handle_step(actor, self.protocol.on_tick(self._context(actor)), pending_proposals)
            self._drain_messages(pending_proposals)
            self._validate_proposals(pending_proposals)
            self._execute_due()
            self._expire_deadlines()
            self._snapshot()
            self.metrics.cycles_completed += 1

        end_time = self.config.duration_steps
        self.world.current_time = end_time
        for risk in sorted(self.world.risk_events.values(), key=lambda item: item.risk_event_id):
            if risk.status == "OPEN":
                risk.status = "UNRESOLVED"
                self.trace.record(end_time, "RISK_UNRESOLVED", {"risk_event": risk.to_dict(include_campaign=True), "reason": "campaign_horizon_ended"}, actor="risk-monitor", entity_ids=sorted(risk.participants()), references={"risk_event_id": risk.risk_event_id})
        final_delivery = max((message.deliver_at for message in self.world.network.queued_messages if message.deliver_at is not None), default=end_time)
        for time_step in range(end_time, final_delivery + 1):
            self.world.current_time = time_step
            self._drain_messages([], allow_protocol=False)

        statuses = [risk.status for risk in self.world.risk_events.values()]
        self.metrics.risks_unresolved = sum(status in {"EXPIRED", "UNRESOLVED"} for status in statuses)
        self.metrics.unresolved_conjunctions = self.metrics.risks_unresolved
        self.metrics.unresolved_high_risk_conjunctions = self.metrics.risks_unresolved
        self.metrics.resolution_probability = self.metrics.risks_resolved / self.metrics.risks_created if self.metrics.risks_created else None
        self.metrics.messages_sent = self.world.network.messages_sent
        self.metrics.messages_delivered = self.world.network.messages_delivered
        self.metrics.messages_dropped = self.world.network.messages_dropped
        self.metrics.messages_delayed_beyond_usefulness = sum(event.event_type == "MESSAGE_DELAYED_BEYOND_USEFULNESS" for event in self.trace.events)
        if self.world.delivered_messages:
            self.metrics.average_communication_latency_steps = sum(message.deliver_at - message.sent_time for message in self.world.delivered_messages) / len(self.world.delivered_messages)
        self.metrics.remaining_fuel_by_agent = {key: agent.state.fuel_budget for key, agent in sorted(self.world.agents.items())}
        for agent_id in self.world.agents:
            self.metrics.per_agent_resource_consumption.setdefault(agent_id, 0.0)
            self.metrics.per_agent_maneuver_burden.setdefault(agent_id, 0)
        self.metrics.maneuver_burden_gini = _gini(self.metrics.per_agent_maneuver_burden.values())
        self.metrics.auction_successes = sum(event.event_type == "MANEUVER_ACCEPTED" and bool(event.payload.get("agent_id")) and self.protocol_name == "auction" for event in self.trace.events)
        self.metrics.auction_timeouts = sum(event.event_type == "AUCTION_TIMED_OUT" for event in self.trace.events)
        self.metrics.auction_no_valid_bids = sum(event.event_type == "AUCTION_NO_VALID_BID" for event in self.trace.events)
        self.metrics.bids_expected = sum(event.payload.get("bids_expected", 0) for event in self.trace.events if event.event_type == "AUCTION_CREATED")
        self.metrics.bids_received = sum(event.event_type == "AUCTION_BID_RECEIVED" for event in self.trace.events)
        self.metrics.total_simulated_resolution_time_steps = self.config.duration_steps
        self.metrics.runtime_seconds = time.perf_counter() - self.started_at
        completed = self.metrics.to_dict(include_extended=True, include_campaign=True)
        completed.pop("runtime_seconds", None)
        self.trace.record(self.world.current_time, "RUN_COMPLETED", {"metrics": completed, "final_risk_statuses": {key: value.status for key, value in sorted(self.world.risk_events.items())}}, actor="simulation", entity_ids=sorted(self.world.agents))
        return {
            "run_id": self.trace.run_id,
            "protocol": self.protocol_name,
            "scenario": self.config.name,
            "agents": self.config.agent_count,
            "seed": self.config.seed,
            "configuration": self.config.to_dict(),
            "initial_risk_events": [risk.to_dict(include_campaign=True) for risk in self.world.risk_events.values() if risk.time == 0],
            "risk_events": [risk.to_dict(include_campaign=True) for risk in self.world.risk_events.values()],
            "maneuver_proposals": [proposal.to_dict() for proposal in self.world.maneuvers.values()],
            "risk_outcomes": self.outcomes,
            "metrics": self.metrics.to_dict(include_extended=True, include_campaign=True),
            "trace": self.trace.to_dict(),
        }


def run_campaign_scenario(config, protocol_name):
    return CampaignRunner(config, protocol_name).run()


__all__ = ["CampaignRunner", "run_campaign_scenario"]
