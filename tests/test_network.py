from src.network.faults import NetworkFaultConfig
from src.network.message import Message, MessageType
from src.network.simulator import NetworkSimulator


def make_message(sender_id="A", recipient_id="B"):
    return Message(
        sender_id=sender_id,
        recipient_id=recipient_id,
        message_type=MessageType.STATE_ADVERTISEMENT,
    )


def test_message_delivery_with_zero_packet_loss():
    network = NetworkSimulator(NetworkFaultConfig(latency_steps=1, packet_loss_rate=0.0, seed=1))

    assert network.send(make_message(), current_time=0)
    assert network.deliver_due(0) == []
    delivered = network.deliver_due(1)

    assert len(delivered) == 1
    assert delivered[0].sender_id == "A"
    assert network.messages_sent == 1
    assert network.messages_delivered == 1
    assert network.messages_dropped == 0


def test_message_dropping_with_full_packet_loss():
    network = NetworkSimulator(NetworkFaultConfig(packet_loss_rate=1.0, seed=1))

    assert not network.send(make_message(), current_time=0)

    assert network.deliver_due(0) == []
    assert network.messages_sent == 1
    assert network.messages_delivered == 0
    assert network.messages_dropped == 1


def test_bandwidth_limit_drops_messages_over_limit():
    network = NetworkSimulator(
        NetworkFaultConfig(packet_loss_rate=0.0, bandwidth_limit_per_agent=1, seed=1)
    )

    assert network.send(make_message(sender_id="A", recipient_id="B"), current_time=0)
    assert not network.send(make_message(sender_id="A", recipient_id="C"), current_time=0)
    assert network.send(make_message(sender_id="A", recipient_id="C"), current_time=1)

    assert network.messages_sent == 2
    assert network.messages_dropped == 1
