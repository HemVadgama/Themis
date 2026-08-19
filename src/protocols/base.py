from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ProtocolDecision:
    coordination_attempts: int = 0
    planned_maneuvers: list[str] = field(default_factory=list)
    unresolved_conjunctions: int = 0
    maneuver_proposals: list = field(default_factory=list)
    rationale: list[dict] = field(default_factory=list)


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


@dataclass(frozen=True)
class CampaignProtocolContext:
    """One actor's immutable campaign view at one simulated timestamp."""

    actor_id: str
    current_time: int
    protocol_name: str
    agent_view: AgentProtocolView | None
    agent_views: dict[str, AgentProtocolView]
    risk_events: tuple
    trajectories: dict
    maneuver_generator: object
    reassessment_horizon_steps: int
    network_latency_steps: int
    auction_weights: dict[str, float]
    global_access: bool = False


@dataclass
class CampaignProtocolStep:
    outbound_messages: list = field(default_factory=list)
    maneuver_proposals: list = field(default_factory=list)
    trace_transitions: list[dict] = field(default_factory=list)

    def extend(self, other):
        self.outbound_messages.extend(other.outbound_messages)
        self.maneuver_proposals.extend(other.maneuver_proposals)
        self.trace_transitions.extend(other.trace_transitions)
        return self


class CampaignCoordinationProtocol(Protocol):
    name: str

    def actors(self, agent_ids: tuple[str, ...]) -> tuple[str, ...]:
        ...

    def on_message(self, message, context: CampaignProtocolContext) -> CampaignProtocolStep:
        ...

    def on_tick(self, context: CampaignProtocolContext) -> CampaignProtocolStep:
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
