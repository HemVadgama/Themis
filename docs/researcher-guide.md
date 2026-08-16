# Researcher guide

Themis is ready for exploratory and comparative computational studies whose question fits the implemented `spacecraft-coordination-v1` abstraction. It is not ready for operational spaceflight decisions or claims about real collision probability. Start by writing the claim you hope to make, then verify that every quantity required by that claim exists in the model and has a documented interpretation.

## Recommended study workflow

1. Read [assumptions and limitations](assumptions-and-limitations.md) and [metrics](metrics.md). Treat omitted physics and information as study boundaries.
2. Copy a curated TOML config and record the scientific question, hypothesis, independent variables, dependent metrics, seed policy, exclusions, and planned comparisons in `experiment.metadata` or an adjacent preregistration.
3. Validate the config with `themis validate`. Archive the resolved config, Themis version, commit, dependency lock or environment export, and source-data versions.
4. Pilot one run and inspect the event trace programmatically or with the read-only viewer. Confirm that the protocol received only intended information and that each measured transition has a trace event.
5. Use `themis compare` for paired qualitative debugging. Use a sweep containing multiple seeds for quantitative claims, then run `themis analyze`.
6. Investigate failed cells and missing values; do not silently discard them. Report model limitations and the number of independent seeds per condition.
7. Re-run selected artifacts from their saved `config.toml` in a clean environment before publication.

## What is stable enough to integrate

- Command-line configuration, run artifacts, and schemas are the primary interoperability contracts.
- `themis.protocols` is the supported protocol-author API. Third-party packages register through a `themis.protocols` entry point.
- `themis.artifacts.load_run()` provides read-only streaming access without the viewer.
- `themis.analysis.analyze_sweep()` provides the same analysis used by the CLI.

The project is pre-1.0. Minor releases may make documented breaking changes with migration notes. Pin the package version for a study and cite that version. `src.*` remains internal unless a document explicitly says otherwise.

## Minimum evidence for a protocol contribution

A contributed or published protocol should include its information assumptions, deterministic tie-breaking, behavior when no valid proposal exists, unit tests for decisions, an integration test through validation/execution, at least one adverse network condition, and repeated-seed results. Protocol code must never mutate physical truth directly.

## Asking for a research capability

Use the research-use-case issue form. State the question, necessary state/action/observation model, expected units, validation reference, scale, and artifact fields required for independent inspection. This makes benchmark growth evidence-driven rather than a collection of unrelated demos.
