# Changelog

This project follows semantic versioning for its documented public contracts. During 0.x, breaking changes increment the minor version.

## 0.4.0 — 2026-08-18

- Add explicit `spacecraft-campaign-v1` without changing v1 configuration, lifecycle, run IDs, metrics, or artifact generation.
- Add multi-cycle propagation, persistent risk lifecycles and beliefs, independent random streams, persistent resources, deadlines, execution effects, secondary risks, and snapshots.
- Add a communication-dependent auction with announcements, bids, deterministic score/tie-break, awards, acknowledgement, reservations, timeout, and fault traces.
- Add campaign protocol hooks, a one-shot adapter, conformance checks, metrics, artifact schema v3, viewer support, and emission validation.
- Add and execute the 36-run network-fault smoke study; add an unexecuted 720-run publication profile.

Compatibility note: v1 still emits artifact schema v2 and retains its scientific identity. Auction requires the explicit campaign benchmark. Loaders now accept v3 as well as older generations.

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
