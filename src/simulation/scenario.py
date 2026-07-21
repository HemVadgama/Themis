from dataclasses import asdict, dataclass, field


@dataclass
class ScenarioConfig:
    name: str
    agent_count: int
    duration_steps: int
    conjunction_threshold_km: float
    seed: int = 0
    network_latency_steps: int = 0
    packet_loss_rate: float = 0.0
    bandwidth_limit_per_agent: int | None = 10
    decision_deadline_steps: int = 2
    risk_reassessment_horizon_steps: int = 4
    maneuver_threshold_km: float | None = None
    secondary_conjunction_threshold_km: float | None = None
    min_delta_v_km_per_step: float = 20.0
    max_delta_v_km_per_step: float = 120.0
    default_fuel_budget: float = 200.0
    execution_failure_rate: float = 0.0
    execution_magnitude_error_fraction: float = 0.0
    allow_secondary_risk: bool = False
    initial_states: list[dict] = field(default_factory=list)
    mission_priorities: dict[str, int] = field(default_factory=dict)
    fuel_budgets: dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        if self.maneuver_threshold_km is None:
            self.maneuver_threshold_km = self.conjunction_threshold_km
        if self.secondary_conjunction_threshold_km is None:
            self.secondary_conjunction_threshold_km = self.conjunction_threshold_km

    def to_dict(self):
        return asdict(self)


def load_scenario(name, seed=0):
    if name == "simple_10":
        return ScenarioConfig(
            name=name,
            agent_count=10,
            duration_steps=6,
            conjunction_threshold_km=1000.0,
            seed=seed,
            network_latency_steps=1,
            packet_loss_rate=0.1,
            bandwidth_limit_per_agent=5,
        )

    if name == "closed_loop_resolved":
        return ScenarioConfig(
            name=name,
            agent_count=2,
            duration_steps=4,
            conjunction_threshold_km=50.0,
            seed=seed,
            network_latency_steps=0,
            packet_loss_rate=0.0,
            bandwidth_limit_per_agent=10,
            decision_deadline_steps=2,
            risk_reassessment_horizon_steps=3,
            min_delta_v_km_per_step=20.0,
            max_delta_v_km_per_step=80.0,
            default_fuel_budget=200.0,
            initial_states=[
                {"agent_id": "SAT-A", "position_km": [0.0, 0.0, 0.0], "velocity_km_per_step": [0.0, 0.0, 0.0]},
                {"agent_id": "SAT-B", "position_km": [30.0, 0.0, 0.0], "velocity_km_per_step": [0.0, 0.0, 0.0]},
            ],
            mission_priorities={"SAT-A": 1, "SAT-B": 5},
        )

    if name == "closed_loop_insufficient_fuel":
        scenario = load_scenario("closed_loop_resolved", seed=seed)
        scenario.name = name
        scenario.fuel_budgets = {"SAT-A": 5.0, "SAT-B": 200.0}
        scenario.mission_priorities = {"SAT-A": 1, "SAT-B": 5}
        return scenario

    if name == "closed_loop_late_response":
        scenario = load_scenario("closed_loop_resolved", seed=seed)
        scenario.name = name
        scenario.network_latency_steps = 3
        scenario.decision_deadline_steps = 1
        return scenario

    if name == "closed_loop_packet_loss":
        scenario = load_scenario("closed_loop_resolved", seed=seed)
        scenario.name = name
        scenario.packet_loss_rate = 1.0
        return scenario

    if name == "closed_loop_secondary":
        return ScenarioConfig(
            name=name,
            agent_count=3,
            duration_steps=4,
            conjunction_threshold_km=50.0,
            seed=seed,
            network_latency_steps=0,
            packet_loss_rate=0.0,
            bandwidth_limit_per_agent=10,
            decision_deadline_steps=2,
            risk_reassessment_horizon_steps=3,
            min_delta_v_km_per_step=20.0,
            max_delta_v_km_per_step=80.0,
            default_fuel_budget=200.0,
            initial_states=[
                {"agent_id": "SAT-A", "position_km": [0.0, 0.0, 0.0], "velocity_km_per_step": [0.0, 0.0, 0.0]},
                {"agent_id": "SAT-B", "position_km": [30.0, 0.0, 0.0], "velocity_km_per_step": [0.0, 0.0, 0.0]},
                {"agent_id": "SAT-C", "position_km": [-160.0, 0.0, 0.0], "velocity_km_per_step": [0.0, 0.0, 0.0]},
            ],
            mission_priorities={"SAT-A": 1, "SAT-B": 5, "SAT-C": 3},
            allow_secondary_risk=True,
        )

    if name == "closed_loop_protocol_difference":
        return ScenarioConfig(
            name=name,
            agent_count=2,
            duration_steps=4,
            conjunction_threshold_km=50.0,
            seed=seed,
            network_latency_steps=0,
            packet_loss_rate=0.0,
            bandwidth_limit_per_agent=10,
            decision_deadline_steps=2,
            risk_reassessment_horizon_steps=3,
            min_delta_v_km_per_step=20.0,
            max_delta_v_km_per_step=80.0,
            default_fuel_budget=200.0,
            initial_states=[
                {"agent_id": "SAT-A", "position_km": [0.0, 0.0, 0.0], "velocity_km_per_step": [0.0, 0.0, 0.0]},
                {"agent_id": "SAT-B", "position_km": [30.0, 0.0, 0.0], "velocity_km_per_step": [0.0, 0.0, 0.0]},
            ],
            mission_priorities={"SAT-A": 1, "SAT-B": 1},
            fuel_budgets={"SAT-A": 60.0, "SAT-B": 200.0},
        )

    if name == "closed_loop_execution_error":
        scenario = load_scenario("closed_loop_resolved", seed=seed)
        scenario.name = name
        scenario.execution_magnitude_error_fraction = 0.1
        return scenario

    raise ValueError(f"Unknown scenario '{name}'")
