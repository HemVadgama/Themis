"""Read-only access to Themis' versioned run-artifact contract."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterator

from src.artifacts import ARTIFACT_SCHEMA_VERSION


class ArtifactError(ValueError):
    """A run directory is missing or violates the supported core contract."""


@dataclass(frozen=True)
class RunArtifacts:
    path: Path
    summary: dict[str, Any]
    metadata: dict[str, Any]
    configuration_text: str

    def events(self) -> Iterator[dict[str, Any]]:
        """Stream events in recorded order without loading the whole trace."""
        event_path = self.path / "events.jsonl"
        try:
            with event_path.open(encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if line.strip():
                        value = json.loads(line)
                        if not isinstance(value, dict):
                            raise ArtifactError(
                                f"Invalid event at {event_path}:{line_number}: expected an object."
                            )
                        yield value
        except json.JSONDecodeError as error:
            raise ArtifactError(
                f"Invalid JSON event at {event_path}:{error.lineno}: {error.msg}."
            ) from error


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ArtifactError(f"Missing required artifact: {path}") from error
    except json.JSONDecodeError as error:
        raise ArtifactError(f"Invalid JSON in {path}: {error.msg}.") from error
    if not isinstance(value, dict):
        raise ArtifactError(f"Invalid artifact {path}: expected a JSON object.")
    return value


def load_run(path: str | Path) -> RunArtifacts:
    """Load and minimally validate a completed run without viewer dependencies."""
    run_path = Path(path).expanduser().resolve()
    if not run_path.is_dir():
        raise ArtifactError(f"Run directory not found: {run_path}")
    summary = _read_object(run_path / "summary.json")
    metadata = _read_object(run_path / "metadata.json")
    required_summary = {"run_id", "scenario", "protocol", "seed", "metrics"}
    missing = sorted(required_summary - set(summary))
    if missing:
        raise ArtifactError(f"Invalid summary.json: missing {', '.join(missing)}.")
    version = metadata.get("artifact_schema_version")
    if not isinstance(version, int) or version < 1:
        raise ArtifactError(f"Invalid artifact_schema_version: {version!r}.")
    if version > ARTIFACT_SCHEMA_VERSION:
        raise ArtifactError(
            f"Artifact schema {version} is newer than supported schema {ARTIFACT_SCHEMA_VERSION}."
        )
    try:
        configuration_text = (run_path / "config.toml").read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ArtifactError(f"Missing required artifact: {run_path / 'config.toml'}") from error
    if not (run_path / "events.jsonl").is_file():
        raise ArtifactError(f"Missing required artifact: {run_path / 'events.jsonl'}")
    return RunArtifacts(run_path, summary, metadata, configuration_text)


def schema_path(name: str) -> Path:
    """Return a packaged JSON Schema path by its documented filename."""
    path = Path(__file__).with_name("schemas") / name
    if not path.is_file() or path.suffix != ".json":
        raise ArtifactError(f"Unknown packaged schema: {name}")
    return path


__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "ArtifactError",
    "RunArtifacts",
    "load_run",
    "schema_path",
]
