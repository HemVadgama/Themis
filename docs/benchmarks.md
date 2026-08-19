# Benchmark policy

`spacecraft-coordination-v1` remains the immutable one-decision benchmark introduced before version 0.4. Its lifecycle, linear local-frame state, threshold risk, action proxy, artifacts, and metric meanings are unchanged. The legacy `run_scenario()` path is retained and explicitly deprecated as a different open-loop simulation; the external v1 CLI continues to use `run_closed_loop_scenario()`.

`spacecraft-campaign-v1` is the explicit multi-cycle successor. It reuses v1's linear state, threshold detector, proposal model, validator, executor, and proxy units, but changes lifecycle semantics: truth propagates every integer cycle, pair risks are deduplicated and updated, messages and beliefs persist, protocols coordinate through deadlines, resources persist, executions alter later truth, and later primary or maneuver-caused secondary risks enter subsequent cycles. It emits artifact/trace schema v3. No valid v1 configuration is reinterpreted.

At equal timestamps campaign ordering is: propagation snapshot; risk creation/update/closure; due-message delivery and belief update; protocol timers; proposal validation; due execution and reassessment; deadline expiration; state snapshot. Zero-latency messages are drained deterministically to quiescence. Delivery order is `(delivery time, sender ID, recipient ID, insertion order)`. A late message is recorded and updates current belief, but is not dispatched to the protocol for an expired decision.

Risk states are `OPEN`, `RESOLVED` (a modeled action clears the target), `CLOSED` (the threshold condition disappears without that attribution), `EXPIRED` (no accepted action by deadline), and `UNRESOLVED` (campaign end). `SUPERSEDED` is reserved for a future explicit replacement transition and campaign v1 never silently emits it. Continuing pairs retain one ID; reappearance after closure gets a generation suffix. `classification` is `SECONDARY` only when a new pair includes a previously maneuvered agent and carries that causal maneuver ID.

A new benchmark is acceptable only when it documents:

- research question and intended/non-intended claims;
- entities, observations, actions, transition rules, time semantics, units, and randomness;
- protocol information boundary and safety/constraint authority;
- reference scenarios with expected qualitative and quantitative behavior;
- metric definitions and validation evidence;
- generic event/reference mappings sufficient for programmatic inspection and the standard viewer;
- deterministic tests and a conformance test against the public artifact contract.

Benchmark implementations must remain independent of `src.viewer`. Domain-specific visualization, if justified, will use a narrow optional renderer hook over standard artifacts. Until that adapter and conformance suite exist, external groups should propose benchmark requirements through the research-use-case issue rather than depend on internal simulation modules.
