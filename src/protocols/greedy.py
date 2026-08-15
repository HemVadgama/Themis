from src.agents.policy import greedy_maneuver_decision
from src.network.message import Message, MessageType
from src.protocols.base import ProtocolDecision


class GreedyProtocol:
    name = "greedy"

    def decide(self, world, conjunctions):
        decision = ProtocolDecision(coordination_attempts=len(conjunctions))
        risky_agents = set()

        for conjunction in conjunctions:
            satellite_a = conjunction["satellite_a"]
            satellite_b = conjunction["satellite_b"]
            risky_agents.add(satellite_a)
            risky_agents.add(satellite_b)

            agent_a = world.agents.get(satellite_a)
            agent_b = world.agents.get(satellite_b)
            if agent_a is None or agent_b is None:
                decision.unresolved_conjunctions += 1
                continue

            agent_a.remember_neighbor(agent_b.agent_id)
            agent_b.remember_neighbor(agent_a.agent_id)

            world.network.send(
                Message(
                    sender_id=agent_a.agent_id,
                    recipient_id=agent_b.agent_id,
                    message_type=MessageType.RISK_ALERT,
                    payload=conjunction,
                ),
                world.current_time,
            )
            world.network.send(
                Message(
                    sender_id=agent_b.agent_id,
                    recipient_id=agent_a.agent_id,
                    message_type=MessageType.RISK_ALERT,
                    payload=conjunction,
                ),
                world.current_time,
            )

        for agent in world.agents.values():
            agent.state.risk_state = "HIGH" if agent.agent_id in risky_agents else "LOW"
            if greedy_maneuver_decision(agent) and agent.plan_maneuver():
                decision.planned_maneuvers.append(agent.agent_id)

        return decision

    def propose_maneuvers(self, context):
        decision = ProtocolDecision(coordination_attempts=len(context.risk_events))
        proposed_pairs = set()

        for view in context.agent_views.values():
            for risk_event_id, risk_event in sorted(view.known_risk_events.items()):
                if risk_event_id in proposed_pairs:
                    continue
                if view.risk_state != "HIGH" or view.fuel_budget <= 0:
                    continue
                if view.agent_id not in risk_event.participants():
                    continue

                proposal = context.maneuver_generator.best_candidate(
                    view.agent_id,
                    risk_event,
                    context.trajectories,
                    context.current_time,
                    self.name,
                    context.reassessment_horizon_steps,
                )
                if proposal is not None:
                    decision.maneuver_proposals.append(proposal)
                    proposed_pairs.add(risk_event_id)
                    decision.rationale.append({"risk_event_id": risk_event_id, "selected_agent_id": view.agent_id, "selection_criterion": "first_eligible_local_view", "known_risk": True, "positive_fuel": True, "outcome": "proposal_created"})

        if not decision.maneuver_proposals and context.risk_events:
            decision.unresolved_conjunctions = len(context.risk_events)
            decision.rationale.append({"selection_criterion": "local_information_only", "outcome": "no_eligible_proposal"})
        elif not context.risk_events:
            decision.rationale.append({"selection_criterion": "local_information_only", "outcome": "no_visible_risk_events"})

        return decision


# TODO: Add auction and gossip protocols once replay and richer fault injection exist.
