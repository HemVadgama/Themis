from dataclasses import dataclass, field
from enum import Enum


class MessageType(str, Enum):
    STATE_ADVERTISEMENT = "STATE_ADVERTISEMENT"
    RISK_ALERT = "RISK_ALERT"
    MANEUVER_INTENT = "MANEUVER_INTENT"
    COORDINATION_REQUEST = "COORDINATION_REQUEST"
    COORDINATION_RESPONSE = "COORDINATION_RESPONSE"


@dataclass
class Message:
    sender_id: str
    recipient_id: str
    message_type: MessageType
    payload: dict = field(default_factory=dict)
    sent_time: int = 0
    deliver_at: int = 0
