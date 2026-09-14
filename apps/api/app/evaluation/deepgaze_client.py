import base64
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import ValidationError

from app.schemas.evaluation import AttentionPrediction, Fixation


@dataclass(frozen=True)
class DeepGazePrediction:
    availability: str
    attention: AttentionPrediction
    heatmap_png: bytes | None


class DeepGazeClient:
    def __init__(self, *, base_url: str, timeout_seconds: float = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def predict(
        self,
        *,
        image_bytes: bytes,
        filename: str = "poster.png",
        steps: int = 5,
    ) -> DeepGazePrediction:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/v1/predict",
                    files={"image": (filename, image_bytes, "image/png")},
                    data={"steps": str(steps)},
                )
        except httpx.HTTPError as error:
            message = f"DeepGaze service is unavailable: {error.__class__.__name__}."
            return self._unavailable(message)
        if response.is_error:
            return self._unavailable(f"DeepGaze service returned HTTP {response.status_code}.")
        try:
            return self._parse_response(response.json())
        except (KeyError, TypeError, ValueError, ValidationError) as error:
            message = f"DeepGaze service returned invalid data: {error.__class__.__name__}."
            return self._unavailable(message)

    def _parse_response(self, payload: dict[str, Any]) -> DeepGazePrediction:
        encoded_heatmap = payload["heatmap_png_base64"]
        if not isinstance(encoded_heatmap, str):
            raise ValueError("heatmap_png_base64 must be a string")
        heatmap_png = base64.b64decode(encoded_heatmap, validate=True)
        cached = bool(payload.get("cached", False))
        attention = AttentionPrediction(
            availability="cached" if cached else "available",
            model=str(payload["model"]),
            device=str(payload["device"]),
            cached=cached,
            fixations=[Fixation.model_validate(item) for item in payload.get("fixations", [])],
            inference_ms=float(payload["inference_ms"]),
        )
        return DeepGazePrediction(
            availability=attention.availability,
            attention=attention,
            heatmap_png=heatmap_png,
        )

    @staticmethod
    def _unavailable(error: str) -> DeepGazePrediction:
        return DeepGazePrediction(
            availability="unavailable",
            attention=AttentionPrediction(availability="unavailable", error=error),
            heatmap_png=None,
        )
