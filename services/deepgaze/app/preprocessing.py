import io

import numpy as np
from PIL import Image, UnidentifiedImageError


class InvalidImageError(ValueError):
    pass


def decode_rgb_image(image_bytes: bytes) -> Image.Image:
    try:
        with Image.open(io.BytesIO(image_bytes)) as opened:
            return opened.convert("RGB")
    except (OSError, UnidentifiedImageError) as error:
        raise InvalidImageError("image must be a readable PNG, JPEG, or WebP file") from error


def image_to_array(image: Image.Image) -> np.ndarray:
    return np.asarray(image, dtype=np.uint8)
