import base64
import io

import numpy as np
from PIL import Image


def encode_heatmap_overlay(image: Image.Image, heatmap: np.ndarray) -> str:
    normalized = _normalize(heatmap)
    color = np.zeros((*normalized.shape, 3), dtype=np.uint8)
    color[..., 0] = (255 * normalized).astype(np.uint8)
    color[..., 1] = (120 * (1 - normalized)).astype(np.uint8)
    color[..., 2] = 40
    overlay = Image.fromarray(color, "RGB").resize(image.size, Image.Resampling.BILINEAR)
    opacity = Image.fromarray((150 * normalized).astype(np.uint8), "L").resize(
        image.size, Image.Resampling.BILINEAR
    )
    composite = Image.composite(overlay, image, opacity)
    buffer = io.BytesIO()
    composite.save(buffer, format="PNG", optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _normalize(heatmap: np.ndarray) -> np.ndarray:
    values = np.nan_to_num(heatmap.astype(np.float32), nan=0, posinf=0, neginf=0)
    minimum, maximum = float(values.min()), float(values.max())
    if maximum <= minimum:
        return np.zeros_like(values)
    return (values - minimum) / (maximum - minimum)
