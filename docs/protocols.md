# Protocol authoring

A protocol receives `ProtocolContext` and returns `ProtocolDecision`. It proposes; it never validates, executes, decrements fuel, or mutates physical truth.

The context contains current simulation time, protocol name, frozen agent views, visible risk events, copied trajectories, a deterministic maneuver generator, reassessment horizon, and a `global_access` declaration. Centralized policies see all agents and risks. Local policies see only agent beliefs populated by delivered messages.

Implement `name` and `propose_maneuvers(context)`. Keep `decide(world, conjunctions)` while the legacy open-loop runner is supported. Return a `ProtocolDecision` with attempts, unresolved counts, and proposals. Use the generator supplied on the context so proposal construction remains compatible with validation.

Start from `src/protocols/example.py`, then add the class to the explicit mapping in `src/protocols/registry.py`. Explicit registration makes selection discoverable and prevents a config from importing arbitrary code.

Protocol code must:

- treat every context value as read-only and avoid global mutable state;
- use only visible risks and agent views;
- make ordering explicit (sort sets/dicts before tie-breaking);
- derive stochastic choices from an injected seeded generator if one is added;
- return proposals before risk deadlines; and
- allow the independent validator and executor to own final state transitions.

Tests should construct a small context, assert proposal choice and unresolved behavior, run the same seed twice, and include an integration run through safety validation. `tests/test_protocols.py` and `tests/test_productization.py` show both levels. Run `themis run CONFIG --protocol your-registered-name` after registration.
