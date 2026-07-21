from dataclasses import asdict, dataclass, field
from enum import Enum


class RiskOutcome(str, Enum):
    RESOLVED = "RESOLVED"
    PARTIALLY_MITIGATED = "PARTIALLY_MITIGATED"
    UNCHANGED = "UNCHANGED"
    WORSENED = "WORSENED"
    SECONDARY_RISK_CREATED = "SECONDARY_RISK_CREATED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    INVALIDATED_BY_NEW_INFORMATION = "INVALIDATED_BY_NEW_INFORMATION"


@dataclass
class RiskEvent:
    risk_event_id: str
    time: int
    satellite_a: str
    satellite_b: str
    distance_km: float
    threshold_km: float
    decision_deadline: int
    status: str = "OPEN"
    metadata: dict = field(default_factory=dict)

    def participants(self) -> set[str]:
        return {self.satellite_a, self.satellite_b}

    def to_dict(self) -> dict:
        return asdict(self)
