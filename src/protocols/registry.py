"""Built-in and installed protocol discovery.

Third-party distributions can advertise a factory or protocol class through the
``themis.protocols`` entry-point group. Configuration never accepts an import
path, so reading an untrusted experiment file cannot import arbitrary modules.
The selected entry point is loaded only when a run constructs that protocol.
"""

from importlib import metadata

from src.protocols.centralized import CentralizedProtocol
from src.protocols.auction import AuctionProtocol
from src.protocols.example import ExampleLowestIdProtocol
from src.protocols.greedy import GreedyProtocol


PROTOCOLS = {
    "auction": AuctionProtocol,
    "centralized": CentralizedProtocol,
    "example-lowest-id": ExampleLowestIdProtocol,
    "greedy": GreedyProtocol,
}


def _external_entry_points():
    discovered = metadata.entry_points()
    if hasattr(discovered, "select"):
        entries = discovered.select(group="themis.protocols")
    else:  # pragma: no cover - Python 3.11+ uses EntryPoints.select
        entries = discovered.get("themis.protocols", ())
    grouped = {}
    for entry in entries:
        if entry.name not in PROTOCOLS:
            grouped.setdefault(entry.name, []).append(entry)
    return grouped


def available_protocols():
    return tuple(sorted(set(PROTOCOLS) | set(_external_entry_points())))


def check_protocol(protocol, expected_name=None):
    """Validate the narrow runtime contract and return *protocol* unchanged."""
    name = getattr(protocol, "name", None)
    if not isinstance(name, str) or not name.strip():
        raise TypeError("A protocol must expose a non-empty string 'name'.")
    if expected_name is not None and name != expected_name:
        raise TypeError(
            f"Protocol entry point '{expected_name}' created a protocol named '{name}'. "
            "The names must match so artifacts remain unambiguous."
        )
    for method in ("decide", "propose_maneuvers"):
        if not callable(getattr(protocol, method, None)):
            raise TypeError(f"Protocol '{name}' must implement {method}().")
    return protocol


def make_protocol(name):
    if name in PROTOCOLS:
        return check_protocol(PROTOCOLS[name](), expected_name=name)
    entries = _external_entry_points().get(name)
    if entries is None:
        choices = ", ".join(available_protocols())
        raise ValueError(f"Unsupported protocol '{name}'. Choose one of: {choices}.")
    if len(entries) > 1:
        providers = ", ".join(sorted(entry.value for entry in entries))
        raise ValueError(
            f"Multiple installed distributions provide protocol '{name}': {providers}. "
            "Uninstall or rename one provider so experiment selection is unambiguous."
        )
    entry = entries[0]
    try:
        factory = entry.load()
        protocol = factory() if callable(factory) else factory
        return check_protocol(protocol, expected_name=name)
    except Exception as error:
        raise ValueError(
            f"Installed protocol '{name}' from {entry.value!r} could not be loaded: {error}"
        ) from error
