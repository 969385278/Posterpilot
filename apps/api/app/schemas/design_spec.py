from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.brief import NonEmptyText
from app.schemas.layout import ElementRole, HexColor, PosterLayout

TemplateId = Literal["campus_lecture", "cultural_event", "club_recruitment"]


class ColorPalette(BaseModel):
    background: HexColor
    primary: HexColor
    secondary: HexColor
    accent: HexColor | None = None


class DesignSpec(BaseModel):
    design_goal: NonEmptyText
    template_id: TemplateId
    expected_attention_path: list[ElementRole] = Field(min_length=1, max_length=8)
    layout: PosterLayout
    palette: ColorPalette
    visual_prompt: NonEmptyText
    negative_prompt: str = Field(default="", max_length=2000)
    knowledge_refs: list[NonEmptyText] = Field(default_factory=list, max_length=20)
    reference_adaptations: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def attention_path_must_reference_layout_roles(self) -> "DesignSpec":
        roles = {element.role for element in self.layout.elements}
        unknown = set(self.expected_attention_path) - roles
        if unknown:
            raise ValueError(
                f"attention path references roles missing from layout: {', '.join(sorted(unknown))}"
            )
        return self
