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
