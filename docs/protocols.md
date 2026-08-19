# Protocol authoring

A protocol receives `ProtocolContext` and returns `ProtocolDecision`. It proposes; it never validates, executes, decrements fuel, or mutates physical truth.

The context contains current simulation time, protocol name, frozen agent views, visible risk events, copied trajectories, a deterministic maneuver generator, reassessment horizon, and a `global_access` declaration. Centralized policies see all agents and risks. Local policies see only agent beliefs populated by delivered messages.

Implement `name` and `propose_maneuvers(context)`. Keep `decide(world, conjunctions)` while the legacy open-loop runner is supported. Return a `ProtocolDecision` with attempts, unresolved counts, and proposals. Use the generator supplied on the context so proposal construction remains compatible with validation.

Start from `src/protocols/example.py`. In-tree protocols can be added to the built-in registry. Independent packages should expose a class or zero-argument factory through Python package metadata:

```toml
[project.entry-points."themis.protocols"]
my-protocol = "my_package.protocol:MyProtocol"
```

Import the contract from `themis.protocols`, and make the implementation's `name` exactly match its entry-point name. `check_protocol(instance)` provides a fast structural check. Installed names are discoverable through `available_protocols()` and work in configuration and CLI selection without frontend changes. The selected entry point is loaded lazily; a TOML file cannot name an arbitrary import path.

Protocol code must:

- treat every context value as read-only and avoid global mutable state;
- use only visible risks and agent views;
- make ordering explicit (sort sets/dicts before tie-breaking);
- derive stochastic choices from an injected seeded generator if one is added;
- return proposals before risk deadlines; and
- allow the independent validator and executor to own final state transitions.

Tests should construct a small context, assert proposal choice and unresolved behavior, run the same seed twice, and include an integration run through safety validation. `tests/test_protocols.py`, `tests/test_productization.py`, and `tests/test_research_api.py` show these levels. Run `themis run CONFIG --protocol your-installed-name` after installation.

## Campaign lifecycle

Campaign-capable protocols additionally implement `actors(agent_ids)`, `on_message(message, context)`, and `on_tick(context)`, returning `CampaignProtocolStep`. Context contains one actor's immutable view, delivered risks and trajectory snapshots, latency, auction weights, and generator. Only the central actor receives `global_access=True`. Steps may return outbound messages, own-agent proposals, and audit transitions; malformed types and sender/agent impersonation are rejected.

Installed entry points retain `decide` and `propose_maneuvers` for registry compatibility. Without campaign hooks, campaign v1 uses a tested one-shot adapter once per delivered local risk. This is the implemented boundary, not broad multi-round interoperability.

```python
from themis.protocols import CampaignProtocolStep, ProtocolDecision

class LocalProtocol:
    name = "local-example"
    def decide(self, world, conjunctions):
        return ProtocolDecision(unresolved_conjunctions=len(conjunctions))
    def propose_maneuvers(self, context):
        return ProtocolDecision(unresolved_conjunctions=len(context.risk_events))
    def actors(self, agent_ids):
        return agent_ids
    def on_message(self, message, context):
        return CampaignProtocolStep()
    def on_tick(self, context):
        return CampaignProtocolStep()
```

Use `check_protocol`, `check_campaign_protocol`, and `check_campaign_step` in package tests. Construct a fresh protocol per run; module globals violate state isolation.

## Built-in auction

The lexicographically first risk participant is auctioneer. Its delivered alert creates `auction:<risk-id>`, names both participants eligible, and sends announcements through the network. A participant with a feasible improving candidate and sufficient unreserved resource creates one bid containing stable IDs, score, factors, and candidate evidence; this reserves it against simultaneous auctions. Collection ends at `decision_deadline − configured_latency − 1`. Valid bids order by `(score, bidder_id, bid_id)`; the winner must receive its award early enough to propose execution by the risk deadline and sends an acknowledgement. Missing announcements, bids, awards, conflicts, no candidate, timeout, and releases are traced. Actual fuel is reserved only after independent validation and consumed only by execution.

Entry-point discovery follows the [PyPA entry-points specification](https://packaging.python.org/en/latest/specifications/entry-points/). Installing an external distribution allows its selected entry point to execute in the current Python process; review and isolate third-party code as you would any research dependency.
