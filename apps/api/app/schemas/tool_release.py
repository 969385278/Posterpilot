from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from app.schemas.design_control import Identifier, StrictModel


class TextOpacityArguments(StrictModel):
    target_ids: list[Identifier] = Field(min_length=1, max_length=3)
    opacity: float = Field(ge=0.3, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def unique_targets(self):
        if len(self.target_ids) != len(set(self.target_ids)):
            raise ValueError("target_ids must be unique")
        return self


class AlignTextGroupArguments(StrictModel):
    target_ids: list[Identifier] = Field(min_length=1, max_length=3)
    reference_id: Identifier
    edge: Literal["left", "center", "right"] = "left"

    @model_validator(mode="after")
    def distinct_targets(self):
        if len(self.target_ids) != len(set(self.target_ids)):
            raise ValueError("target_ids must be unique")
        if self.reference_id in self.target_ids:
            raise ValueError("reference_id must not also be a target")
        return self


class ToolReviewRequest(StrictModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    expected_revision: int = Field(ge=0, strict=True)
    action: Literal["publish", "withdraw"]
    note: str = Field(min_length=1, max_length=1000)
    reviewer: str = Field(min_length=1, max_length=80)
    report_id: UUID | None = None
    implementation_reviewed: bool = False


class GapTriageRequest(StrictModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    expected_revision: int = Field(ge=1, strict=True)
    category: Literal["strategy_error", "capability_gap", "infrastructure", "unclassified"]
    note: str = Field(min_length=1, max_length=1000)
    resolution_case_id: UUID | None = None
    resolution_case_ids: list[UUID] = Field(default_factory=list, max_length=500)
    resolution_tool: str | None = Field(default=None, min_length=1, max_length=80)

    @model_validator(mode="after")
    def unique_resolution_sources(self):
        ids = self.resolution_case_ids + (
            [self.resolution_case_id] if self.resolution_case_id else []
        )
        if len(ids) != len(set(ids)):
            raise ValueError("resolution sources must be unique")
        return self
