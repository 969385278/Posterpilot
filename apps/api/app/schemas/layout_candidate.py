from pydantic import Field

from app.schemas.design_control import Identifier, PosterAnalysis, StrictModel, VerificationCheck
from app.schemas.evaluation import AttentionPrediction
from app.schemas.layout import PosterLayout


class LayoutCandidate(StrictModel):
    id: Identifier
    round_number: int = Field(ge=0, le=3)
    label: str
    poster_artifact: str
    layout: PosterLayout
    analysis: PosterAnalysis
    attention: AttentionPrediction
    checks: list[VerificationCheck] = Field(default_factory=list)
    subject_overlap: float | None = None
    rank_score: float = Field(ge=0, le=100)
    attention_used_for_ranking: bool = False
    is_current: bool = False
    selectable: bool = True
    notes: list[str] = Field(default_factory=list)
