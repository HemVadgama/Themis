from dataclasses import dataclass, field
import random

from src.network.faults import NetworkFaultConfig


@dataclass
class NetworkSimulator:
    config: NetworkFaultConfig
    queued_messages: list = field(default_factory=list)
    messages_sent: int = 0
    messages_delivered: int = 0
    messages_dropped: int = 0

    def __post_init__(self):
        self._random = random.Random(self.config.seed)
        self._send_counts = {}

    def send(self, message, current_time):
        key = (current_time, message.sender_id)
        sent_this_tick = self._send_counts.get(key, 0)

        if (
            self.config.bandwidth_limit_per_agent is not None
            and sent_this_tick >= self.config.bandwidth_limit_per_agent
        ):
            self.messages_dropped += 1
            return False

        self._send_counts[key] = sent_this_tick + 1
        self.messages_sent += 1

        if self._random.random() < self.config.packet_loss_rate:
            self.messages_dropped += 1
            return False

        message.sent_time = current_time
        message.deliver_at = current_time + self.config.latency_steps
        self.queued_messages.append(message)
        self.queued_messages.sort(key=lambda queued: (queued.deliver_at, queued.sender_id, queued.recipient_id))
        return True

    def deliver_due(self, current_time):
        delivered = []
        remaining = []

        for message in self.queued_messages:
            if message.deliver_at <= current_time:
                delivered.append(message)
            else:
                remaining.append(message)

        self.queued_messages = remaining
        self.messages_delivered += len(delivered)
        return delivered
