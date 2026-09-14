from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.brief import NonEmptyText

OptimizationActionName = Literal[
    "set_position",
    "set_size",
    "set_font_size",
    "set_color",
    "set_line_spacing",
    "set_alignment",
    "set_opacity",
    "set_brightness",
    "regenerate_visual",
]


class OptimizationAction(BaseModel):
    action: OptimizationActionName
    target_id: NonEmptyText
    parameters: dict[str, Any] = Field(default_factory=dict)
    reason: NonEmptyText
    source_rule_ids: list[NonEmptyText] = Field(default_factory=list, max_length=20)


class OptimizationPlan(BaseModel):
    target_issues: list[NonEmptyText] = Field(min_length=1, max_length=20)
    actions: list[OptimizationAction] = Field(min_length=1, max_length=20)
    regenerate_visual: bool = False

