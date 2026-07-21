from dataclasses import dataclass, field


@dataclass
class WorldState:
    agents: dict
    network: object
    current_time: int = 0
    trajectories: dict = field(default_factory=dict)
    original_trajectories: dict = field(default_factory=dict)
    maneuvers: dict = field(default_factory=dict)
    risk_events: dict = field(default_factory=dict)
    trace: object | None = None
    conjunctions: list[dict] = field(default_factory=list)
    delivered_messages: list = field(default_factory=list)

    def reset_agent_plans(self):
        for agent in self.agents.values():
            agent.clear_plan()
