import numpy as np

from app.schemas import FixationPrediction


def sample_fixations(heatmap: np.ndarray, *, steps: int) -> list[FixationPrediction]:
    if heatmap.ndim != 2 or heatmap.size == 0:
        raise ValueError("heatmap must be a non-empty two-dimensional array")
    scores = np.nan_to_num(heatmap.astype(np.float32), nan=0, posinf=0, neginf=0).copy()
    height, width = scores.shape
    radius = max(2, min(height, width) // 12)
    fixations: list[FixationPrediction] = []
    for order in range(1, steps + 1):
        y, x = np.unravel_index(np.argmax(scores), scores.shape)
        fixations.append(
            FixationPrediction(
                x=round((float(x) + 0.5) / width, 6),
                y=round((float(y) + 0.5) / height, 6),
                order=order,
            )
        )
        top, bottom = max(0, y - radius), min(height, y + radius + 1)
        left, right = max(0, x - radius), min(width, x + radius + 1)
        scores[top:bottom, left:right] = scores.min() - 1
    return fixations
