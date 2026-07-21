from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ProtocolDecision:
    coordination_attempts: int = 0
    planned_maneuvers: list[str] = field(default_factory=list)
    unresolved_conjunctions: int = 0
    maneuver_proposals: list = field(default_factory=list)


@dataclass(frozen=True)
class AgentProtocolView:
    agent_id: str
    fuel_budget: float
    mission_priority: int
    risk_state: str
    known_risk_events: dict
    known_neighbors: set[str]


@dataclass(frozen=True)
class ProtocolContext:
    current_time: int
    protocol_name: str
    agent_views: dict[str, AgentProtocolView]
    risk_events: list
    trajectories: dict
    maneuver_generator: object
    reassessment_horizon_steps: int
    global_access: bool = False


class CoordinationProtocol(Protocol):
    name: str

    def decide(self, world, conjunctions) -> ProtocolDecision:
        ...

    def propose_maneuvers(self, context: ProtocolContext) -> ProtocolDecision:
        ...


def make_agent_view(agent):
    return AgentProtocolView(
        agent_id=agent.agent_id,
        fuel_budget=agent.state.fuel_budget,
        mission_priority=agent.state.mission_priority,
        risk_state=agent.state.risk_state,
        known_risk_events=dict(agent.state.known_risk_events),
        known_neighbors=set(agent.state.known_neighbors),
    )
