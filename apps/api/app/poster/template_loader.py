import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.paths import DEFAULT_TEMPLATE_DIRECTORY
from app.schemas.brief import CanvasSize, PosterBrief
from app.schemas.layout import (
    Alignment,
    ElementRole,
    HexColor,
    LayoutElement,
    NormalizedBox,
    PosterLayout,
)


class UnknownTemplateError(ValueError):
    pass


class TemplateSlot(BaseModel):
    id: str
    role: ElementRole
    box: NormalizedBox
    font_size: int | None = Field(default=None, ge=10, le=240)
    font_family: str | None = None
    color: HexColor | None = None
    alignment: Alignment = "left"
    line_spacing: float = Field(default=1.2, ge=0.8, le=3.0)


class PosterTemplate(BaseModel):
    id: str
    canvas: CanvasSize
    slots: list[TemplateSlot] = Field(min_length=1)


class TemplateLoader:
    def __init__(self, template_directory: Path | str = DEFAULT_TEMPLATE_DIRECTORY):
        self.template_directory = Path(template_directory)

    def list_template_ids(self) -> list[str]:
        return sorted(path.stem for path in self.template_directory.glob("*.json"))

    def instantiate(self, template_id: str, brief: PosterBrief) -> PosterLayout:
        template = self._load(template_id)
        elements = [
            LayoutElement(
                id=slot.id,
                role=slot.role,
                content=_content_for_role(slot.role, brief),
                box=slot.box,
                font_size=slot.font_size,
                font_family=slot.font_family,
                color=slot.color,
                alignment=slot.alignment,
                line_spacing=slot.line_spacing,
            )
            for slot in template.slots
            if slot.role not in {"subtitle", "event_info", "organizer"}
            or _content_for_role(slot.role, brief)
        ]
        return PosterLayout(canvas=template.canvas, elements=elements)

    def _load(self, template_id: str) -> PosterTemplate:
        path = self.template_directory / f"{template_id}.json"
        if not path.is_file():
            raise UnknownTemplateError(f"Unknown poster template: {template_id}")
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise UnknownTemplateError(f"Invalid poster template: {template_id}") from error
        template = PosterTemplate.model_validate(data)
        if template.id != template_id:
            raise UnknownTemplateError(f"Template ID mismatch: {template_id}")
        return template


def _content_for_role(role: ElementRole, brief: PosterBrief) -> str | None:
    if role == "title":
        return brief.title
    if role == "subtitle":
        return brief.subtitle
    if role == "event_info":
        return "\n".join(value for value in (brief.event_time, brief.location) if value)
    if role == "organizer":
        return f"主办：{brief.organizer}" if brief.organizer else None
    return None
