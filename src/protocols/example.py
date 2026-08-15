"""Minimal reference protocol for authors to copy and adapt."""

from src.protocols.base import ProtocolDecision


class ExampleLowestIdProtocol:
    """Ask the lexicographically first participant to maneuver for each visible risk."""

    name = "example-lowest-id"

    def decide(self, world, conjunctions):
        """Legacy open-loop hook retained for compatibility with the original arena."""
        return ProtocolDecision(
            coordination_attempts=len(conjunctions),
            unresolved_conjunctions=len(conjunctions),
        )

    def propose_maneuvers(self, context):
        decision = ProtocolDecision(coordination_attempts=len(context.risk_events))
        for risk in context.risk_events:
            agent_id = min(risk.participants())
            if agent_id not in context.agent_views:
                decision.unresolved_conjunctions += 1
                decision.rationale.append({"risk_event_id": risk.risk_event_id, "selected_agent_id": agent_id, "selection_criterion": "lexicographically_first_participant", "outcome": "agent_not_visible"})
                continue
            proposal = context.maneuver_generator.best_candidate(
                agent_id,
                risk,
                context.trajectories,
                context.current_time,
                self.name,
                context.reassessment_horizon_steps,
            )
            if proposal is None:
                decision.unresolved_conjunctions += 1
                decision.rationale.append({"risk_event_id": risk.risk_event_id, "selected_agent_id": agent_id, "selection_criterion": "lexicographically_first_participant", "outcome": "no_improving_candidate"})
            else:
                decision.maneuver_proposals.append(proposal)
                decision.rationale.append({"risk_event_id": risk.risk_event_id, "selected_agent_id": agent_id, "selection_criterion": "lexicographically_first_participant", "outcome": "proposal_created"})
        return decision
