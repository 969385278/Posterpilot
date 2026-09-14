import base64

import respx
from httpx import Response

from app.evaluation.deepgaze_client import DeepGazeClient


@respx.mock
async def test_client_maps_prediction_response_to_a_typed_result() -> None:
    route = respx.post("http://deepgaze.test/v1/predict").mock(
        return_value=Response(
            200,
            json={
                "model": "DeepGaze III",
                "device": "cuda",
                "cached": False,
                "fixations": [{"x": 0.3, "y": 0.2, "order": 1}],
                "heatmap_png_base64": base64.b64encode(b"png").decode(),
                "inference_ms": 42.5,
            },
        )
    )
    client = DeepGazeClient(base_url="http://deepgaze.test", timeout_seconds=5)

    result = await client.predict(image_bytes=b"png-bytes", filename="poster.png", steps=3)

    assert route.called
    assert result.availability == "available"
    assert result.attention.model == "DeepGaze III"
    assert result.attention.fixations[0].order == 1
    assert result.heatmap_png == b"png"


@respx.mock
async def test_client_returns_an_unavailable_result_when_service_is_down() -> None:
    route = respx.post("http://deepgaze.test/v1/predict")
    route.mock(return_value=Response(503, json={"detail": "off"}))
    client = DeepGazeClient(base_url="http://deepgaze.test", timeout_seconds=5)

    result = await client.predict(image_bytes=b"png-bytes", filename="poster.png", steps=3)

    assert result.availability == "unavailable"
    assert result.attention.error == "DeepGaze service returned HTTP 503."
    assert result.heatmap_png is None
