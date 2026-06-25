from dataclasses import dataclass, field


@dataclass
class WorldState:
    agents: dict
    network: object
    current_time: int = 0
    conjunctions: list[dict] = field(default_factory=list)
    delivered_messages: list = field(default_factory=list)

    def reset_agent_plans(self):
        for agent in self.agents.values():
            agent.clear_plan()
