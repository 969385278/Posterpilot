from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class GeneratedImage:
    image_url: str
    provider: str
    model: str
    retried_without_reference: bool = False


class ImageProvider(Protocol):
    async def generate(
        self,
        prompt: str,
        *,
        size: str | None = None,
        reference_image_url: str = "",
    ) -> GeneratedImage: ...

