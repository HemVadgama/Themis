from dataclasses import asdict, dataclass, field


@dataclass
class TraceEvent:
    time: int
    sequence: int
    event_type: str
    payload: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


class SimulationTrace:
    def __init__(self, run_id, scenario_id, protocol, seed, configuration):
        self.run_id = run_id
        self.scenario_id = scenario_id
        self.protocol = protocol
        self.seed = seed
        self.configuration = configuration
        self.events = []
        self._sequence = 0

    def record(self, time_step, event_type, payload=None):
        event = TraceEvent(
            time=time_step,
            sequence=self._sequence,
            event_type=event_type,
            payload=payload or {},
        )
        self._sequence += 1
        self.events.append(event)
        return event

    def to_dict(self):
        return {
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "protocol": self.protocol,
            "seed": self.seed,
            "configuration": self.configuration,
            "events": [event.to_dict() for event in self.events],
        }


def format_trace_summary(trace_data):
    lines = [
        f"Run: {trace_data.get('run_id')}",
        f"Scenario: {trace_data.get('scenario_id')}",
        f"Protocol: {trace_data.get('protocol')}",
        f"Seed: {trace_data.get('seed')}",
        "Events:",
    ]
    for event in trace_data.get("events", []):
        lines.append(f"{event['time']:>4} #{event['sequence']:>3} {event['event_type']} {event.get('payload', {})}")
    return "\n".join(lines)
