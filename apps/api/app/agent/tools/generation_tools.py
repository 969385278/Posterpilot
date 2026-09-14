import base64
from pathlib import Path

import httpx

from app.providers.image.base import GeneratedImage


async def materialize_generated_image(
    generated: GeneratedImage,
    *,
    output_path: Path | str,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image_bytes = await _load_image_bytes(generated.image_url)
    output.write_bytes(image_bytes)
    return output


async def _load_image_bytes(image_url: str) -> bytes:
    if image_url.startswith("data:image/"):
        try:
            _, encoded = image_url.split(",", 1)
            return base64.b64decode(encoded, validate=True)
        except (ValueError, UnicodeEncodeError) as error:
            raise ValueError("Generated image data URL is invalid.") from error
    if image_url.startswith(("https://", "http://")):
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.get(image_url)
        if response.is_error:
            raise ValueError(f"Generated image download returned HTTP {response.status_code}.")
        if not response.content:
            raise ValueError("Generated image download was empty.")
        return response.content
    raise ValueError("Generated image uses an unsupported URL scheme.")
