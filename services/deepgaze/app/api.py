from time import perf_counter
from typing import Annotated, Any

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.cache import PredictionCache, cache_key
from app.fixation_sampler import sample_fixations
from app.heatmap import encode_heatmap_overlay
from app.model import ModelUnavailableError, SaliencyModel
from app.preprocessing import InvalidImageError, decode_rgb_image, image_to_array
from app.schemas import PredictResponse


def build_router(*, model: SaliencyModel, cache: PredictionCache) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/predict", response_model=PredictResponse)
    async def predict(
        image: Annotated[UploadFile, File(...)],
        steps: Annotated[int, Form()] = 5,
    ) -> dict[str, Any]:
        if not 1 <= steps <= 20:
            raise HTTPException(status_code=422, detail="steps must be between 1 and 20")
        image_bytes = await image.read()
        key = cache_key(image_bytes, steps=steps, model_config=model.config_id)
        cached = cache.get(key)
        if cached is not None:
            cached["cached"] = True
            return cached
        start = perf_counter()
        try:
            poster = decode_rgb_image(image_bytes)
            heatmap = _as_heatmap(model.predict(image_to_array(poster)))
        except InvalidImageError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except ModelUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        inference_ms = round((perf_counter() - start) * 1000, 3)
        result = PredictResponse(
            model=model.model_name,
            device=model.device,
            cached=False,
            fixations=sample_fixations(heatmap, steps=steps),
            heatmap_png_base64=encode_heatmap_overlay(poster, heatmap),
            inference_ms=inference_ms,
        ).model_dump()
        cache.set(key, result)
        return result

    return router


def _as_heatmap(values: np.ndarray) -> np.ndarray:
    if values.ndim != 2 or values.size == 0:
        raise ModelUnavailableError("DeepGaze returned an invalid saliency map.")
    return values
