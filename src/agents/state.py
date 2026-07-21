from dataclasses import dataclass, field


@dataclass
class SatelliteAgentState:
    agent_id: str
    satellite_name: str
    position: dict | None = None
    fuel_budget: float = 100.0
    reserved_fuel: float = 0.0
    mission_priority: int = 1
    known_neighbors: set[str] = field(default_factory=set)
    active_conjunctions: set[str] = field(default_factory=set)
    known_risk_events: dict = field(default_factory=dict)
    known_neighbor_state: dict = field(default_factory=dict)
    pending_coordination_requests: list = field(default_factory=list)
    pending_maneuver_proposals: list = field(default_factory=list)
    accepted_maneuver: str | None = None
    maneuver_history: list[str] = field(default_factory=list)
    last_observation_time: int | None = None
    last_communication_time: int | None = None
    safety_state: str = "NOMINAL"
    risk_state: str = "LOW"
    planned_action: str = "NONE"
