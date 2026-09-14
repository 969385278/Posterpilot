import io

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app


class FakeSaliencyModel:
    model_name = "fake-deepgaze"
    device = "cpu"
    config_id = "fake-v1"

    def predict(self, image: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]
        result = np.zeros((height, width), dtype=np.float32)
        result[height // 2, width // 2] = 1
        return result


def _poster_bytes() -> bytes:
    image = Image.new("RGB", (64, 96), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_predict_returns_fixations_heatmap_and_cache_state() -> None:
    client = TestClient(create_app(model=FakeSaliencyModel()))
    files = {"image": ("poster.png", _poster_bytes(), "image/png")}

    first = client.post("/v1/predict", files=files, data={"steps": "3"})
    second = client.post("/v1/predict", files=files, data={"steps": "3"})

    assert first.status_code == 200
    first_data = first.json()
    assert first_data["model"] == "fake-deepgaze"
    assert first_data["cached"] is False
    assert len(first_data["fixations"]) == 3
    assert first_data["heatmap_png_base64"]
    assert first_data["inference_ms"] >= 0
    assert second.json()["cached"] is True
