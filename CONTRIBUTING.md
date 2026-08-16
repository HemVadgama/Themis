# Contributing to Themis

Set up Python 3.11 or 3.12 with `python -m pip install ".[dev]"`, then run `python -m pytest`. Reinstall after changing packaged CLI code. Before submitting a change, also run the basic example and any example affected by your work.

Preserve the boundaries described in `docs/architecture.md`: protocols propose, the validator decides admissibility, the executor owns truth/fuel mutation, and metrics observe. New stochastic behavior must accept a controlled random source or derive from the experiment seed. New physical quantities must state units and whether they are measurements, derived values, or proxies. Public integration code belongs under `themis.*`; avoid exposing another `src.*` path.

Good first contributions include a protocol plus deterministic tests, a documented linear scenario, an honest metric derived from existing state, an artifact-based visualizer, or an input adapter that does not bypass validation. Avoid claiming operational realism without implementation and validation evidence.

Use `docs/protocols.md` for protocol work and `docs/configuration.md` when changing the schema. Artifact changes must update packaged JSON Schemas and compatibility tests. Update example smoke tests, changelog, and user documentation with public-interface changes. Report bugs or modeling concerns with the relevant issue form; include a resolved config and Themis version when possible.
