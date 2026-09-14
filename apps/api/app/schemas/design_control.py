"""Shared vocabulary for case selection, HITL controls, tools and verification.

This module deliberately does not import brief/layout models: PosterBrief embeds
these types, while layout already depends on PosterBrief's primitive types.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$")]
TraitKey = Literal["background_contrast", "background_saturation", "title_emphasis"]
TraitDirection = Literal["preserve", "strengthen", "weaken"]
ReferenceAspect = Literal["palette", "typography", "composition", "hierarchy"]
PriorityRole = Literal["title", "subtitle", "main_visual", "event_info", "organizer"]
LockProperty = Literal["content", "position", "typography"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ReferenceSelection(StrictModel):
    case_id: Identifier
    aspects: list[ReferenceAspect] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def unique_aspects(self):
        if len(set(self.aspects)) != len(self.aspects):
            raise ValueError("reference aspects must be unique")
        return self


class TraitAdjustment(StrictModel):
    trait: TraitKey
    direction: TraitDirection
    strength: float = Field(default=0.2, ge=0.1, le=0.5)


class ElementLock(StrictModel):
    element_id: Identifier
    properties: list[LockProperty] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def unique_properties(self):
        if len(set(self.properties)) != len(self.properties):
            raise ValueError("lock properties must be unique")
        return self


class DesignControls(StrictModel):
    adjustments: list[TraitAdjustment] = Field(default_factory=list, max_length=3)
    locks: list[ElementLock] = Field(default_factory=list, max_length=32)
    attention_priority: list[PriorityRole] = Field(default_factory=list, max_length=5)
    selected_candidate_id: Identifier | None = None

    @model_validator(mode="after")
    def unique_targets(self):
        for values, description in (
            ([item.trait for item in self.adjustments], "trait adjustments"),
            ([item.element_id for item in self.locks], "locked elements"),
            (self.attention_priority, "attention priorities"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{description} must be unique")
        return self

    @property
    def has_request(self) -> bool:
        return bool(self.adjustments or self.locks or self.attention_priority or self.selected_candidate_id)


class BackgroundTreatment(StrictModel):
    """Absolute factors applied to the immutable source, never repeatedly to output."""

    contrast: float = Field(default=1.0, ge=0.35, le=1.65)
    saturation: float = Field(default=1.0, ge=0.0, le=1.65)


class BackgroundAdjustmentArguments(StrictModel):
    contrast: float | None = Field(default=None, ge=0.35, le=1.65)
    saturation: float | None = Field(default=None, ge=0.0, le=1.65)

    @model_validator(mode="after")
    def require_adjustment(self):
        if self.contrast is None and self.saturation is None:
            raise ValueError("adjust_background requires contrast or saturation")
        return self


class FeatureObservation(StrictModel):
    key: Literal["background_contrast", "background_saturation", "title_emphasis", "information_density"]
    label: str
    value: float | None
    unit: str
    basis: Literal["image_measurement", "render_metadata", "model_judgment"]
    explanation: str
    controllable: bool = False


class RenderedTextFact(StrictModel):
    element_id: str
    content: str
    requested_font_size: int
    actual_font_size: int
    font_name: str
    color: str
    line_count: int
    fits_box: bool
    box: dict[str, int]


class PosterAnalysis(StrictModel):
    version: str = "design-analysis-v1"
    features: list[FeatureObservation] = Field(default_factory=list)
    palette: list[str] = Field(default_factory=list)
    text_facts: list[RenderedTextFact] = Field(default_factory=list)
    visual_summary: str = ""
    visual_summary_basis: Literal["model_judgment"] = "model_judgment"
    warnings: list[str] = Field(default_factory=list)
    readability_checks: list["VerificationCheck"] = Field(default_factory=list)


class VerificationCheck(StrictModel):
    key: str
    label: str
    status: Literal["passed", "failed", "unavailable"]
    detail: str
    before: float | None = None
    after: float | None = None


class GoalVerification(StrictModel):
    checks: list[VerificationCheck] = Field(default_factory=list)
    outcome: Literal["met", "not_met", "unverified", "no_change_requested"]
    summary: str
