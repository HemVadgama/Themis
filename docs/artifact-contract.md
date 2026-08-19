# Artifact contract

Every completed run is a directory containing `config.toml`, `summary.json`, `metrics.csv`, `events.jsonl`, and `metadata.json`. The viewer is one consumer of these files; it does not own or extend the contract.

## Compatibility rules

- `artifact_schema_version` in metadata identifies the core artifact generation.
- Consumers must reject a newer unsupported generation and tolerate unknown properties within a supported generation.
- Event identity is the ordered pair `(time, sequence)`. `event_type` and `category` are generic routing surfaces; `payload` is event-specific.
- `entity_ids` supports generic entity indexing. `references` links decisions, messages, risks, proposals, validation, and execution without frontend-only fields.
- Metrics may expand. Consumers should select names they understand and retain unknown values when round-tripping.
- Created time, runtime, git discovery, and filesystem paths are observational and not model outputs.

The package includes JSON Schema Draft 2020-12 documents for metadata, summary, events, and sweep analysis. Locate them with:

```python
from themis.artifacts import schema_path

print(schema_path("event-v2.schema.json"))
```

JSON Schema's official [specification](https://json-schema.org/specification) defines the validation vocabulary. Themis schemas deliberately keep event payloads and metrics extensible so protocol contributors do not need viewer changes.

## Read-only programmatic access

```python
from themis.artifacts import load_run

run = load_run("results/example-run")
for event in run.events():
    print(event["time"], event["event_type"], event["references"])
```

The loader validates core presence and version compatibility and streams JSONL. It never invokes simulation or viewer code and never writes to the run directory.

Artifact v3 is emitted only by `spacecraft-campaign-v1`; v1 continues to emit v2. Existing v1/v2 artifacts remain readable and the maximum supported generation is three. Packaged `metadata-v3`, `summary-v3`, and `event-v3` schemas add campaign identity while retaining extensible payloads and metrics. Emission validates required fields, versions, deterministic event identity, unique entity IDs, and string causal references before completion.

Campaign events link risk, message, auction, bid, award, and maneuver IDs. `STATE_SNAPSHOT` records trajectories, risk objects/statuses, remaining/reserved resources, and each actor's known risk/trajectory IDs. Auction score evidence and message transitions explain winner, timeout, and delivery failures. Late messages remain visible and never enter an earlier snapshot.
