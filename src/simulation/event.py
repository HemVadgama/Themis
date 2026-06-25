from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(order=True)
class SimulationEvent:
    time: int
    priority: int
    sequence: int
    event_type: str = field(compare=False)
    callback: Callable | None = field(default=None, compare=False)
    payload: dict[str, Any] = field(default_factory=dict, compare=False)
