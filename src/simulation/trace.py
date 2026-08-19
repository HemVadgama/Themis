from dataclasses import asdict, dataclass, field


TRACE_SCHEMA_VERSION = 2

EVENT_CATEGORIES = {
    "RUN_STARTED": "experiment",
    "RUN_COMPLETED": "experiment",
    "STATE_UPDATED": "state",
    "AGENT_STATE_UPDATED": "observation",
    "CONJUNCTION_DETECTED": "risk",
    "CONJUNCTION_RESOLVED": "risk",
    "RISK_REASSESSED": "reassessment",
    "SECONDARY_CONJUNCTION_DETECTED": "risk",
    "MESSAGE_SENT": "communication",
    "MESSAGE_DELIVERED": "communication",
    "MESSAGE_DROPPED": "failure",
    "MESSAGE_DELAYED_BEYOND_USEFULNESS": "failure",
    "PROTOCOL_DECISION": "decision",
    "COORDINATION_TIMEOUT": "failure",
    "MANEUVER_PROPOSED": "action",
    "MANEUVER_VALIDATED": "validation",
    "MANEUVER_REJECTED": "validation",
    "MANEUVER_ACCEPTED": "validation",
    "MANEUVER_SCHEDULED": "action",
    "MANEUVER_EXECUTED": "execution",
    "MANEUVER_FAILED": "failure",
    "TRAJECTORY_REPROPAGATED": "state",
    "RESOURCE_UPDATED": "resource",
    "CYCLE_STARTED": "experiment",
    "RISK_CREATED": "risk",
    "RISK_UPDATED": "risk",
    "RISK_CLOSED": "risk",
    "RISK_EXPIRED": "risk",
    "RISK_UNRESOLVED": "risk",
    "AUCTION_CREATED": "auction",
    "AUCTION_ANNOUNCED": "auction",
    "AUCTION_BID_CREATED": "auction",
    "AUCTION_BID_RECEIVED": "auction",
    "AUCTION_WINNER_SELECTED": "auction",
    "AUCTION_AWARD_SENT": "auction",
    "AUCTION_AWARD_RECEIVED": "auction",
    "AUCTION_ACKNOWLEDGED": "auction",
    "AUCTION_TIMED_OUT": "failure",
    "AUCTION_NO_VALID_BID": "failure",
    "PROTOCOL_RESOURCE_RESERVED": "resource",
    "PROTOCOL_RESOURCE_RELEASED": "resource",
    "STATE_SNAPSHOT": "state",
}


@dataclass
class TraceEvent:
    time: int
    sequence: int
    event_type: str
    payload: dict = field(default_factory=dict)
    category: str | None = None
    actor: str | None = None
    entity_ids: list[str] = field(default_factory=list)
    references: dict[str, str] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


class SimulationTrace:
    def __init__(self, run_id, scenario_id, protocol, seed, configuration, schema_version=TRACE_SCHEMA_VERSION):
        self.run_id = run_id
        self.scenario_id = scenario_id
        self.protocol = protocol
        self.seed = seed
        self.configuration = configuration
        self.schema_version = schema_version
        self.events = []
        self._sequence = 0

    def record(self, time_step, event_type, payload=None, *, category=None, actor=None, entity_ids=None, references=None):
        event = TraceEvent(
            time=time_step,
            sequence=self._sequence,
            event_type=event_type,
            payload=payload or {},
            category=category or EVENT_CATEGORIES.get(event_type, "other"),
            actor=actor,
            entity_ids=list(entity_ids or []),
            references=dict(references or {}),
        )
        self._sequence += 1
        self.events.append(event)
        return event

    def to_dict(self):
        return {
            "trace_schema_version": self.schema_version,
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
