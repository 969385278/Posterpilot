import hashlib
import json
from typing import Any


def cache_key(image_bytes: bytes, *, steps: int, model_config: str) -> str:
    digest = hashlib.sha256()
    digest.update(image_bytes)
    digest.update(b"\0")
    config = {"steps": steps, "model_config": model_config}
    config_bytes = json.dumps(config, sort_keys=True).encode()
    digest.update(config_bytes)
    return digest.hexdigest()


class PredictionCache:
    """Small process-local cache; callers own any persistent cache policy."""

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        entry = self._entries.get(key)
        return dict(entry) if entry is not None else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._entries[key] = dict(value)
