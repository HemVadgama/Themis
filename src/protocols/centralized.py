from src.protocols.base import ProtocolDecision


class CentralizedProtocol:
    name = "centralized"

    def decide(self, world, conjunctions):
        decision = ProtocolDecision(coordination_attempts=len(conjunctions))

        for conjunction in conjunctions:
            agent_a = world.agents.get(conjunction["satellite_a"])
            agent_b = world.agents.get(conjunction["satellite_b"])

            if agent_a is None or agent_b is None:
                decision.unresolved_conjunctions += 1
                continue

            selected = self._select_maneuvering_agent(agent_a, agent_b)
            if selected.plan_maneuver():
                decision.planned_maneuvers.append(selected.agent_id)
            else:
                decision.unresolved_conjunctions += 1

        return decision

    def _select_maneuvering_agent(self, agent_a, agent_b):
        if agent_a.state.mission_priority != agent_b.state.mission_priority:
            if agent_a.state.mission_priority < agent_b.state.mission_priority:
                return agent_a
            return agent_b

        if agent_a.state.fuel_budget >= agent_b.state.fuel_budget:
            return agent_a
        return agent_b

    def propose_maneuvers(self, context):
        decision = ProtocolDecision(coordination_attempts=len(context.risk_events))

        for risk_event in context.risk_events:
            view_a = context.agent_views.get(risk_event.satellite_a)
            view_b = context.agent_views.get(risk_event.satellite_b)
            if view_a is None or view_b is None:
                decision.unresolved_conjunctions += 1
                continue

            selected = self._select_view(view_a, view_b)
            proposal = context.maneuver_generator.best_candidate(
                selected.agent_id,
                risk_event,
                context.trajectories,
                context.current_time,
                self.name,
                context.reassessment_horizon_steps,
            )
            if proposal is None:
                decision.unresolved_conjunctions += 1
            else:
                decision.maneuver_proposals.append(proposal)

        return decision

    def _select_view(self, view_a, view_b):
        if view_a.mission_priority != view_b.mission_priority:
            if view_a.mission_priority < view_b.mission_priority:
                return view_a
            return view_b

        if view_a.fuel_budget >= view_b.fuel_budget:
            return view_a
        return view_b
