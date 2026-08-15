from dataclasses import asdict, dataclass


@dataclass
class MetricsSummary:
    original_conjunctions: int = 0
    resolved_conjunctions: int = 0
    unresolved_conjunctions: int = 0
    worsened_conjunctions: int = 0
    secondary_conjunctions_created: int = 0
    minimum_pre_maneuver_separation_km: float | None = None
    minimum_post_maneuver_separation_km: float | None = None
    safety_validation_failures: int = 0
    conjunctions_detected: int = 0
    coordination_attempts: int = 0
    successful_agreements: int = 0
    timeouts: int = 0
    conflicting_maneuver_intents: int = 0
    duplicate_maneuver_proposals: int = 0
    fallback_activations: int = 0
    planned_maneuvers: int = 0
    maneuvers_proposed: int = 0
    maneuvers_executed: int = 0
    maneuvers_rejected: int = 0
    maneuvers_failed: int = 0
    messages_sent: int = 0
    messages_delivered: int = 0
    messages_dropped: int = 0
    messages_delayed_beyond_usefulness: int = 0
    average_communication_latency_steps: float | None = None
    estimated_fuel_used: float = 0.0
    total_delta_v_used_km_per_step: float = 0.0
    delta_v_per_resolved_conjunction: float | None = None
    mission_disruption_cost: float = 0.0
    per_agent_maneuver_burden: dict = None
    remaining_fuel_by_agent: dict = None
    unresolved_high_risk_conjunctions: int = 0
    detection_to_decision_time_steps: list = None
    decision_to_execution_time_steps: list = None
    total_simulated_resolution_time_steps: int | None = None
    runtime_seconds: float = 0.0

    def __post_init__(self):
        if self.per_agent_maneuver_burden is None:
            self.per_agent_maneuver_burden = {}
        if self.remaining_fuel_by_agent is None:
            self.remaining_fuel_by_agent = {}
        if self.detection_to_decision_time_steps is None:
            self.detection_to_decision_time_steps = []
        if self.decision_to_execution_time_steps is None:
            self.decision_to_execution_time_steps = []

    def to_dict(self, include_extended=False):
        data = asdict(self)
        if include_extended:
            return data

        legacy_fields = (
            "conjunctions_detected",
            "coordination_attempts",
            "planned_maneuvers",
            "messages_sent",
            "messages_delivered",
            "messages_dropped",
            "estimated_fuel_used",
            "unresolved_high_risk_conjunctions",
            "runtime_seconds",
        )
        return {field: data[field] for field in legacy_fields}
