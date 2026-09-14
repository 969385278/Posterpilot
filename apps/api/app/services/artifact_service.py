import json
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from app.schemas.run import ArtifactReference, RunEvent

SAFE_ARTIFACT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
MEDIA_TYPES = {
    ".json": "application/json",
    ".jsonl": "application/x-ndjson",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


class ArtifactService:
    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def run_directory(self, run_id: UUID) -> Path:
        directory = self.root / str(run_id)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def write_json(self, run_id: UUID, name: str, payload: Any) -> ArtifactReference:
        path = self._artifact_path(run_id, name)
        serialized = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(f"{serialized}\n", encoding="utf-8")
        temporary.replace(path)
        return self._reference(run_id, path)

    def write_bytes(self, run_id: UUID, name: str, payload: bytes) -> ArtifactReference:
        path = self._artifact_path(run_id, name)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_bytes(payload)
        temporary.replace(path)
        return self._reference(run_id, path)

    def append_event(self, event: RunEvent) -> ArtifactReference:
        path = self._artifact_path(event.run_id, "events.jsonl")
        serialized = event.model_dump_json()
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{serialized}\n")
        return self._reference(event.run_id, path)

    def list_run_artifacts(self, run_id: UUID) -> list[ArtifactReference]:
        return [
            self._reference(run_id, path)
            for path in self.run_directory(run_id).iterdir()
            if path.is_file() and SAFE_ARTIFACT_NAME.fullmatch(path.name)
        ]

    def _artifact_path(self, run_id: UUID, name: str) -> Path:
        if not SAFE_ARTIFACT_NAME.fullmatch(name):
            raise ValueError("artifact name must be a plain safe filename")
        return self.run_directory(run_id) / name

    @staticmethod
    def _reference(run_id: UUID, path: Path) -> ArtifactReference:
        return ArtifactReference(
            name=path.name,
            relative_path=f"{run_id}/{path.name}",
            media_type=MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"),
        )
