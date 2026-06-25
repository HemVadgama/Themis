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


# TODO: Add auction and gossip protocols once replay and richer fault injection exist.
