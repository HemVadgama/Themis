# Researcher guide

Themis supports exploratory and comparative computational studies across two explicitly versioned benchmark lifecycles. Use `spacecraft-coordination-v1` for the stable one-decision experiment and `spacecraft-campaign-v1` when later decisions must depend on persistent truth, delivered beliefs, resources, risk generations, deadlines, and protocol state. Start by writing the question you want to answer, then verify that the required quantities exist in the selected model and have documented interpretations.

## Recommended study workflow

1. Read the benchmark [assumptions](assumptions-and-limitations.md) and [metrics](metrics.md) to confirm that they fit the study.
2. Select and record the benchmark version before choosing a protocol. Copy a curated TOML config and record the scientific question, hypothesis, independent variables, dependent metrics, seed policy, exclusions, and planned comparisons in `experiment.metadata` or an adjacent preregistration.
3. Validate the config with `themis validate`. Archive the resolved config, Themis version, commit, dependency lock or environment export, and source-data versions.
4. Pilot one run and inspect the event trace programmatically or with the read-only viewer. Confirm that the protocol received only intended information and that each measured transition has a trace event.
5. Use `themis compare` for paired qualitative debugging. Use a sweep containing multiple seeds for quantitative claims, then run `themis analyze`.
6. Investigate failed cells and missing values; do not silently discard them. Report the number of independent seeds per condition.
7. Re-run selected artifacts from their saved `config.toml` in a clean environment before publication.

For a complete campaign example, run `examples/campaign.toml`. The executable [auction/network-fault study](../studies/auction-network-faults/README.md) demonstrates paired protocol comparisons, resumable execution, deterministic result verification, uncertainty reporting, boundary scans, and causal inspection of failed auctions. Its three-seed smoke output is workflow evidence; do not treat it as a powered confirmatory result.

## What is stable enough to integrate

- Command-line configuration, run artifacts, and schemas are the primary interoperability contracts.
- `themis.protocols` is the supported protocol-author API. Third-party packages register through a `themis.protocols` entry point.
- `themis.artifacts.load_run()` provides read-only streaming access without the viewer.
- `themis.analysis.analyze_sweep()` provides the same analysis used by the CLI.

Artifact schema v2 remains the output contract for `spacecraft-coordination-v1`; campaign runs emit v3. The public loader reads both. Existing protocols keep the one-decision `decide`/`propose_maneuvers` contract; campaign-native protocols add actor-scoped `actors`, `on_message`, and `on_tick` hooks. Read the [protocol guide](protocols.md) before claiming campaign interoperability.

The project is pre-1.0. Minor releases may make documented breaking changes with migration notes. Pin the package version for a study and cite that version. `src.*` remains internal unless a document explicitly says otherwise.

## Minimum evidence for a protocol contribution

A contributed or published protocol should include its information assumptions, deterministic tie-breaking, behavior when no valid proposal exists, unit tests for decisions, an integration test through validation/execution, at least one adverse network condition, and repeated-seed results. Campaign protocols should also test malformed steps, actor isolation, late delivery, timeout/release behavior, and fresh per-run state. Protocol code must never mutate physical truth directly.

## Asking for a research capability

Use the research-use-case issue form. State the question, necessary state/action/observation model, expected units, validation reference, scale, and artifact fields required for independent inspection. This makes benchmark growth evidence-driven rather than a collection of unrelated demos.
