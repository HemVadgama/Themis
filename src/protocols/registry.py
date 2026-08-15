"""Built-in protocol registry.

External protocols should implement ``CoordinationProtocol`` and be added here.
Keeping registration explicit makes experiment selection inspectable and avoids
executing arbitrary modules named in untrusted configuration files.
"""

from src.protocols.centralized import CentralizedProtocol
from src.protocols.example import ExampleLowestIdProtocol
from src.protocols.greedy import GreedyProtocol


PROTOCOLS = {
    "centralized": CentralizedProtocol,
    "example-lowest-id": ExampleLowestIdProtocol,
    "greedy": GreedyProtocol,
}


def available_protocols():
    return tuple(sorted(PROTOCOLS))


def make_protocol(name):
    try:
        protocol_type = PROTOCOLS[name]
    except KeyError as error:
        choices = ", ".join(available_protocols())
        raise ValueError(f"Unsupported protocol '{name}'. Choose one of: {choices}.") from error
    return protocol_type()
