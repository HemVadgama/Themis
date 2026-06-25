from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ProtocolDecision:
    coordination_attempts: int = 0
    planned_maneuvers: list[str] = field(default_factory=list)
    unresolved_conjunctions: int = 0


class CoordinationProtocol(Protocol):
    name: str

    def decide(self, world, conjunctions) -> ProtocolDecision:
        ...
