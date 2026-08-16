# Themis vision

Themis is an inspectable experimentation framework for coordination in networked autonomous systems. It is designed around a research question, not a particular frontend: how do decision protocols behave when participants have incomplete information, communication faults, deadlines, resource constraints, independent safety checks, and imperfect execution?

The first implemented benchmark, `spacecraft-coordination-v1`, uses simplified local-frame linear trajectories and threshold proximity events. It is useful for controlled protocol experiments; it does not establish reductions in real orbital collision risk. Higher-fidelity physics and additional domains must enter through explicit, validated benchmark adapters rather than by silently changing this benchmark's meaning.

## Design commitments

- A complete resolved configuration, controlled seed, machine-readable event trace, metrics, and provenance accompany every run.
- Protocols see declared information and propose actions; separate validator and executor components retain authority over simulated truth.
- Batch analysis treats seeds as replicates and states its statistical assumptions.
- Core execution, programmatic analysis, and extension do not depend on the optional read-only viewer.
- Public claims are limited to behaviors represented and tested by the implementation.

## Growth path

The near-term objective is a credible protocol research testbed: independently packaged protocols, versioned artifact schemas, benchmark conformance requirements, richer uncertainty models, and published validation studies. Multi-domain support is a target, not a current claim. Each new benchmark must document its state/action model, units, assumptions, reference cases, metrics, and validation evidence.
