from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.brief import NonEmptyText
from app.schemas.layout import ElementRole, NormalizedBox

Severity = Literal["low", "medium", "high", "critical"]
EvaluationAvailability = Literal["available", "cached", "unavailable"]


class RuleIssue(BaseModel):
    rule_id: NonEmptyText
    problem: NonEmptyText
    severity: Severity
    evidence: NonEmptyText
    affected_elements: list[NonEmptyText] = Field(default_factory=list)
    suggested_action_types: list[NonEmptyText] = Field(default_factory=list)


class Fixation(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    order: int = Field(ge=1)
    aoi_role: ElementRole | None = None


class AttentionPrediction(BaseModel):
    availability: EvaluationAvailability
    model: str | None = None
    device: str | None = None
    cached: bool = False
    fixations: list[Fixation] = Field(default_factory=list)
    predicted_path: list[ElementRole] = Field(default_factory=list)
    heatmap_artifact: str | None = None
    inference_ms: float | None = Field(default=None, ge=0)
    error: str | None = None


class VisionIssue(BaseModel):
    problem: NonEmptyText
    reason: NonEmptyText
    severity: Severity
    related_principles: list[NonEmptyText] = Field(default_factory=list)
    suggested_actions: list[NonEmptyText] = Field(default_factory=list)


class VisionReview(BaseModel):
    availability: EvaluationAvailability
    score: float | None = Field(default=None, ge=0, le=100)
    summary: str = ""
    issues: list[VisionIssue] = Field(default_factory=list)
    error: str | None = None
    subject_regions: list[NormalizedBox] = Field(default_factory=list, max_length=6)


class ScoreBreakdown(BaseModel):
    hard_rules: float = Field(ge=0, le=40)
    vision: float | None = Field(default=None, ge=0, le=35)
    attention: float | None = Field(default=None, ge=0, le=25)
    total: float = Field(ge=0, le=100)
    available_weight: float = Field(ge=0, le=100)


class EvaluationReport(BaseModel):
    rule_issues: list[RuleIssue] = Field(default_factory=list)
    attention: AttentionPrediction
    vision: VisionReview
    scores: ScoreBreakdown
    primary_issues: list[NonEmptyText] = Field(default_factory=list)
    evaluator_version: NonEmptyText
    design_goal_context: dict = Field(default_factory=dict)
