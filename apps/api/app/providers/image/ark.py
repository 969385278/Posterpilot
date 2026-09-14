from typing import Any
from urllib.parse import urlparse

import httpx

from app.providers.image.base import GeneratedImage


class ArkImageResponseError(RuntimeError):
    pass


class ArkImageProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        default_size: str,
        response_format: str = "url",
        output_format: str = "jpeg",
        timeout_seconds: float = 90,
    ):
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.default_size = default_size
        self.response_format = response_format
        self.output_format = output_format
        self.timeout_seconds = timeout_seconds

    async def generate(
        self,
        prompt: str,
        *,
        size: str | None = None,
        reference_image_url: str = "",
    ) -> GeneratedImage:
        self._require_configuration()
        first_result = await self._generate_once(
            prompt,
            size=size,
            reference_image_url=reference_image_url,
        )
        if first_result is not None:
            return first_result
        if not _is_http_url(reference_image_url):
            raise ArkImageResponseError("Ark returned no image URL or base64 image data.")

        retried = await self._generate_once(prompt, size=size, reference_image_url="")
        if retried is None:
            message = "Ark returned no image URL or base64 image data after retry."
            raise ArkImageResponseError(message)
        return GeneratedImage(
            image_url=retried.image_url,
            provider=retried.provider,
            model=retried.model,
            retried_without_reference=True,
        )

    async def _generate_once(
        self,
        prompt: str,
        *,
        size: str | None,
        reference_image_url: str,
    ) -> GeneratedImage | None:
        payload = self._build_payload(
            prompt,
            size=size or self.default_size,
            reference_image_url=reference_image_url,
        )
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/images/generations",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.HTTPError as error:
            message = self._sanitize(f"Ark image request failed: {error}")
            raise ArkImageResponseError(message) from error

        if response.is_error:
            if reference_image_url and response.status_code in {400, 422}:
                return None
            detail = response.text.strip() or "No error detail returned."
            message = self._sanitize(f"Ark image returned HTTP {response.status_code}: {detail}")
            raise ArkImageResponseError(message)

        try:
            image = response.json()["data"][0]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            message = "Ark returned an unexpected image response shape."
            raise ArkImageResponseError(message) from error
        image_url = image.get("url") if isinstance(image, dict) else None
        if isinstance(image_url, str) and image_url:
            return GeneratedImage(image_url=image_url, provider="ark", model=self.model)
        encoded = image.get("b64_json") if isinstance(image, dict) else None
        if isinstance(encoded, str) and encoded:
            return GeneratedImage(
                image_url=f"data:image/png;base64,{encoded}",
                provider="ark",
                model=self.model,
            )
        return None

    def _build_payload(
        self,
        prompt: str,
        *,
        size: str,
        reference_image_url: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "size": size,
            "response_format": self.response_format,
        }
        if _is_http_url(reference_image_url):
            payload["image"] = reference_image_url
        if self.model.startswith("doubao-seedream-5-0"):
            payload["output_format"] = self.output_format
        return payload

    def _require_configuration(self) -> None:
        if not self.api_key:
            raise ArkImageResponseError("Ark API key is not configured.")
        if not self.model:
            raise ArkImageResponseError("Ark image model is not configured.")

    def _sanitize(self, message: str) -> str:
        return message.replace(self.api_key, "[redacted]") if self.api_key else message


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
