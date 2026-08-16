# Benchmark policy

`spacecraft-coordination-v1` is the only implemented benchmark in version 0.3. It fixes the interpretation of the current scenario lifecycle, linear local-frame state, threshold risk, action proxy, and metrics. Scenario presets vary initial conditions and faults; they are not separate benchmark domains.

A new benchmark is acceptable only when it documents:

- research question and intended/non-intended claims;
- entities, observations, actions, transition rules, time semantics, units, and randomness;
- protocol information boundary and safety/constraint authority;
- reference scenarios with expected qualitative and quantitative behavior;
- metric definitions and validation evidence;
- generic event/reference mappings sufficient for programmatic inspection and the standard viewer;
- deterministic tests and a conformance test against the public artifact contract.

Benchmark implementations must remain independent of `src.viewer`. Domain-specific visualization, if justified, will use a narrow optional renderer hook over standard artifacts. Until that adapter and conformance suite exist, external groups should propose benchmark requirements through the research-use-case issue rather than depend on internal simulation modules.
