from typing import Any, Protocol


class VisionJsonProvider(Protocol):
    async def analyze_json(self, *, image_url: str, prompt: str) -> dict[str, Any]: ...

