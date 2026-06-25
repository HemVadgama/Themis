from dataclasses import dataclass


@dataclass
class NetworkFaultConfig:
    latency_steps: int = 0
    packet_loss_rate: float = 0.0
    bandwidth_limit_per_agent: int | None = None
    seed: int = 0

    def __post_init__(self):
        if self.latency_steps < 0:
            raise ValueError("latency_steps cannot be negative")
        if not 0.0 <= self.packet_loss_rate <= 1.0:
            raise ValueError("packet_loss_rate must be between 0.0 and 1.0")
        if self.bandwidth_limit_per_agent is not None and self.bandwidth_limit_per_agent < 0:
            raise ValueError("bandwidth_limit_per_agent cannot be negative")
