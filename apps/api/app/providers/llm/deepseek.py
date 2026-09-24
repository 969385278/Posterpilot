import json
from collections.abc import Sequence
from typing import Any, Literal

import httpx

from app.providers.llm.base import ChatMessage


class ProviderResponseError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        kind: Literal[
            "unavailable", "timeout", "transport", "http", "invalid_response"
        ] = "transport",
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code


class DeepSeekProvider:
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

    async def complete_json(self, messages: Sequence[ChatMessage]) -> dict[str, Any]:
        if not self.api_key:
            raise ProviderResponseError("DeepSeek API key is not configured.", kind="unavailable")
        if not self.model:
            raise ProviderResponseError(
                "DeepSeek text model is not configured.", kind="unavailable",
            )

        payload = {
            "model": self.model,
            "messages": list(messages),
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "stream": False,
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
        except httpx.TimeoutException as error:
            raise ProviderResponseError("DeepSeek request timed out.", kind="timeout") from error
        except httpx.HTTPError as error:
            message = self._sanitize(f"DeepSeek request failed: {error}")
            raise ProviderResponseError(message) from error

        if response.is_error:
            detail = response.text.strip() or "No error detail returned."
            raise ProviderResponseError(
                self._sanitize(f"DeepSeek returned HTTP {response.status_code}: {detail}"),
                kind="http", status_code=response.status_code,
            )

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            message = "DeepSeek returned an unexpected response shape."
            raise ProviderResponseError(message, kind="invalid_response") from error
        if not isinstance(content, str) or not content.strip():
            raise ProviderResponseError(
                "DeepSeek returned no message content.", kind="invalid_response",
            )
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as error:
            raise ProviderResponseError(
                "DeepSeek did not return a valid JSON object.", kind="invalid_response",
            ) from error
        if not isinstance(parsed, dict):
            raise ProviderResponseError(
                "DeepSeek did not return a valid JSON object.", kind="invalid_response",
            )
        return parsed

    def _sanitize(self, message: str) -> str:
        return message.replace(self.api_key, "[redacted]") if self.api_key else message
