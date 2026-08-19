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
    cycles_completed: int = 0
    risks_created: int = 0
    risks_resolved: int = 0
    risks_closed: int = 0
    risks_expired: int = 0
    risks_unresolved: int = 0
    primary_risks_created: int = 0
    secondary_risks_created: int = 0
    resolution_probability: float | None = None
    risk_resolution_time_steps: list = None
    decisions_completed_before_deadline: int = 0
    decision_deadline_misses: int = 0
    proposals_accepted: int = 0
    proposals_rejected: int = 0
    execution_failures: int = 0
    maneuver_count: int = 0
    modeled_maneuver_cost: float = 0.0
    auction_successes: int = 0
    auction_timeouts: int = 0
    auction_no_valid_bids: int = 0
    bids_expected: int = 0
    bids_received: int = 0
    resource_exhaustion_events: int = 0
    per_agent_resource_consumption: dict = None
    maneuver_burden_gini: float | None = None
    peak_concurrent_open_risks: int = 0

    def __post_init__(self):
        if self.per_agent_maneuver_burden is None:
            self.per_agent_maneuver_burden = {}
        if self.remaining_fuel_by_agent is None:
            self.remaining_fuel_by_agent = {}
        if self.detection_to_decision_time_steps is None:
            self.detection_to_decision_time_steps = []
        if self.decision_to_execution_time_steps is None:
            self.decision_to_execution_time_steps = []
        if self.risk_resolution_time_steps is None:
            self.risk_resolution_time_steps = []
        if self.per_agent_resource_consumption is None:
            self.per_agent_resource_consumption = {}

    def to_dict(self, include_extended=False, include_campaign=False):
        data = asdict(self)
        if include_extended:
            if include_campaign:
                return data
            campaign_fields = {
                "cycles_completed", "risks_created", "risks_resolved", "risks_closed",
                "risks_expired", "risks_unresolved", "primary_risks_created",
                "secondary_risks_created", "resolution_probability", "risk_resolution_time_steps",
                "decisions_completed_before_deadline", "decision_deadline_misses",
                "proposals_accepted", "proposals_rejected", "execution_failures",
                "maneuver_count", "modeled_maneuver_cost", "auction_successes",
                "auction_timeouts", "auction_no_valid_bids", "bids_expected", "bids_received",
                "resource_exhaustion_events", "per_agent_resource_consumption",
                "maneuver_burden_gini", "peak_concurrent_open_risks",
            }
            return {key: value for key, value in data.items() if key not in campaign_fields}

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
