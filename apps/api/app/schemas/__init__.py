"""Validated domain contracts shared by the API and agent graph."""

from app.schemas.brief import CanvasSize, PosterBrief
from app.schemas.design_spec import DesignSpec
from app.schemas.evaluation import EvaluationReport
from app.schemas.optimization import OptimizationPlan
from app.schemas.run import RunEvent, RunRecord

__all__ = [
    "CanvasSize",
    "DesignSpec",
    "EvaluationReport",
    "OptimizationPlan",
    "PosterBrief",
    "RunEvent",
    "RunRecord",
]

