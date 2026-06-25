from dataclasses import asdict, dataclass


@dataclass
class MetricsSummary:
    conjunctions_detected: int = 0
    coordination_attempts: int = 0
    planned_maneuvers: int = 0
    messages_sent: int = 0
    messages_delivered: int = 0
    messages_dropped: int = 0
    estimated_fuel_used: float = 0.0
    unresolved_high_risk_conjunctions: int = 0
    runtime_seconds: float = 0.0

    def to_dict(self):
        return asdict(self)
