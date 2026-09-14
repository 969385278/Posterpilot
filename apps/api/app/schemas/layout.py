from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.schemas.brief import CanvasSize, NonEmptyText

HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
ElementRole = Literal[
    "title",
    "subtitle",
    "main_visual",
    "event_info",
    "organizer",
    "logo",
    "qr",
    "decoration",
]
Alignment = Literal["left", "center", "right"]


class NormalizedBox(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def remain_inside_canvas(self) -> "NormalizedBox":
        epsilon = 1e-9
        if self.x + self.width > 1 + epsilon or self.y + self.height > 1 + epsilon:
            raise ValueError("element box must remain inside canvas bounds")
        return self


class LayoutElement(BaseModel):
    id: NonEmptyText
    role: ElementRole
    box: NormalizedBox
    content: str | None = None
    font_size: int | None = Field(default=None, ge=10, le=240)
    font_family: str | None = None
    color: HexColor | None = None
    alignment: Alignment = "left"
    line_spacing: float = Field(default=1.2, ge=0.8, le=3.0)
    opacity: float = Field(default=1.0, ge=0, le=1)

    @model_validator(mode="after")
    def require_content_for_text_element(self) -> "LayoutElement":
        text_roles = {"title", "subtitle", "event_info", "organizer"}
        if self.role in text_roles and not (self.content and self.content.strip()):
            raise ValueError(f"{self.role} element requires content")
        return self


class PosterLayout(BaseModel):
    canvas: CanvasSize
    elements: list[LayoutElement] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def require_unique_ids_and_core_roles(self) -> "PosterLayout":
        element_ids = [element.id for element in self.elements]
        if len(element_ids) != len(set(element_ids)):
            raise ValueError("layout element ids must be unique")

        roles = {element.role for element in self.elements}
        missing = {"title", "main_visual"} - roles
        if missing:
            raise ValueError(f"layout is missing core roles: {', '.join(sorted(missing))}")
        return self
