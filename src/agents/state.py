from dataclasses import dataclass, field


@dataclass
class SatelliteAgentState:
    agent_id: str
    satellite_name: str
    position: dict | None = None
    fuel_budget: float = 100.0
    mission_priority: int = 1
    known_neighbors: set[str] = field(default_factory=set)
    risk_state: str = "LOW"
    planned_action: str = "NONE"
