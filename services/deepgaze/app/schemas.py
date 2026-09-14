from pydantic import BaseModel, Field


class FixationPrediction(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    order: int = Field(ge=1)


class PredictResponse(BaseModel):
    model: str
    device: str
    cached: bool
    fixations: list[FixationPrediction]
    heatmap_png_base64: str
    inference_ms: float = Field(ge=0)
