from dataclasses import asdict, dataclass, field
from enum import Enum


class ManeuverStatus(str, Enum):
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    ACCEPTED = "ACCEPTED"
    SCHEDULED = "SCHEDULED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ValidationStatus(str, Enum):
    NOT_EVALUATED = "NOT_EVALUATED"
    VALID = "VALID"
    INVALID = "INVALID"


@dataclass
class ManeuverProposal:
    maneuver_id: str
    agent_id: str
    risk_event_id: str
    proposal_time: int
    planned_execution_time: int
    maneuver_frame: str
    delta_v_magnitude_km_per_step: float
    delta_v_vector_km_per_step: tuple[float, float, float]
    estimated_fuel_cost: float
    expected_mission_disruption_score: float
    protocol: str
    expected_post_maneuver_separation_km: float | None = None
    proposal_status: str = ManeuverStatus.PROPOSED.value
    validation_status: str = ValidationStatus.NOT_EVALUATED.value
    acceptance_reason: str | None = None
    rejection_reason: str | None = None
    execution_status: str = "NOT_EXECUTED"
    actual_delta_v_vector_km_per_step: tuple[float, float, float] | None = None
    actual_execution_time: int | None = None
    actual_execution_error: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["delta_v_vector_km_per_step"] = list(self.delta_v_vector_km_per_step)
        if self.actual_delta_v_vector_km_per_step is not None:
            data["actual_delta_v_vector_km_per_step"] = list(self.actual_delta_v_vector_km_per_step)
        return data
