# Changelog

This project follows semantic versioning for its documented public contracts. During 0.x, breaking changes increment the minor version.

## 0.3.0 — 2026-08-15

- Add stable `themis.protocols`, `themis.artifacts`, and `themis.analysis` Python APIs.
- Discover independently packaged protocols through lazy `themis.protocols` entry points.
- Add versioned benchmark identity and preserve the actual scenario preset in resolved configs.
- Add packaged JSON Schemas and a read-only streaming artifact loader.
- Add replicate-aware sweep analysis with explicit 95% Student-t interval assumptions.
- Correct the viewer's event-time reconstruction and improve run, comparison, and sweep visual evidence.
- Add researcher onboarding, methodology, ecosystem positioning, citation metadata, release guidance, and community templates.

Migration note: run IDs change because benchmark identity and the correct preset now participate in resolved configuration hashing. Existing version-1/2 artifacts remain readable; rerunning an old resolved config under 0.3 creates the 0.3 identity.

## 0.2.0

- Add strict TOML configuration, deterministic run IDs, structured run artifacts, comparisons, resumable sweeps, and the artifact-driven local viewer.
