from dataclasses import dataclass


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

    raise ValueError(f"Unknown scenario '{name}'")
