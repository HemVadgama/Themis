from dataclasses import dataclass, field

from src.agents.state import SatelliteAgentState


@dataclass
class SatelliteAgent:
    agent_id: str
    satellite_name: str
    fuel_budget: float = 100.0
    mission_priority: int = 1
    state: SatelliteAgentState = field(init=False)
    inbox: list = field(default_factory=list)

    def __post_init__(self):
        self.state = SatelliteAgentState(
            agent_id=self.agent_id,
            satellite_name=self.satellite_name,
            fuel_budget=self.fuel_budget,
            mission_priority=self.mission_priority,
        )

    def update_position(self, position):
        self.state.position = position

    def remember_neighbor(self, agent_id):
        if agent_id != self.agent_id:
            self.state.known_neighbors.add(agent_id)

    def plan_maneuver(self):
        if self.state.fuel_budget <= 0:
            self.state.planned_action = "NONE"
            return False

        self.state.planned_action = "MANEUVER"
        return True

    def clear_plan(self):
        self.state.planned_action = "NONE"
