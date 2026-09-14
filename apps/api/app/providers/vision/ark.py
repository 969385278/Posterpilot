import json
import re
from typing import Any

import httpx


class ArkVisionResponseError(RuntimeError):
    pass


class ArkVisionProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float = 60,
    ):
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def analyze_json(self, *, image_url: str, prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise ArkVisionResponseError("Ark API key is not configured.")
        if not self.model:
            raise ArkVisionResponseError("Ark vision model is not configured.")
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.HTTPError as error:
            message = self._sanitize(f"Ark vision request failed: {error}")
            raise ArkVisionResponseError(message) from error
        if response.is_error:
            detail = response.text.strip() or "No error detail returned."
            message = self._sanitize(f"Ark vision returned HTTP {response.status_code}: {detail}")
            raise ArkVisionResponseError(message)
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            message = "Ark vision returned an unexpected response shape."
            raise ArkVisionResponseError(message) from error
        if not isinstance(content, str) or not content.strip():
            raise ArkVisionResponseError("Ark vision returned no message content.")
        content = content.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", content, flags=re.DOTALL)
        if fenced:
            content = fenced.group(1)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as error:
            message = "Ark vision did not return a valid JSON object."
            raise ArkVisionResponseError(message) from error
        if not isinstance(parsed, dict):
            raise ArkVisionResponseError("Ark vision did not return a valid JSON object.")
        return parsed

    def _sanitize(self, message: str) -> str:
        return message.replace(self.api_key, "[redacted]") if self.api_key else message
