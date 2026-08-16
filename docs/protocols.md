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

Entry-point discovery follows the [PyPA entry-points specification](https://packaging.python.org/en/latest/specifications/entry-points/). Installing an external distribution allows its selected entry point to execute in the current Python process; review and isolate third-party code as you would any research dependency.
