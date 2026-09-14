from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator
from app.schemas.design_control import PriorityRole, ReferenceSelection

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PosterType = Literal["campus_lecture", "cultural_event", "club_recruitment"]


class CanvasSize(BaseModel):
    width: int = Field(ge=640, le=4096)
    height: int = Field(ge=640, le=4096)

    @model_validator(mode="after")
    def require_vertical_canvas(self) -> "CanvasSize":
        if self.height <= self.width:
            raise ValueError("MVP requires a vertical canvas")
        return self


class PosterBrief(BaseModel):
    poster_type: PosterType = "cultural_event"
    topic: str = ""
    target_audience: str = ""
    title: NonEmptyText
    title_font: Literal["auto", "standard", "mashanzheng", "longcang", "zhimangxing", "zcoolkuaile", "zcoolqingkehuangyou", "zcoolxiaowei"] = "auto"
    subtitle: NonEmptyText | None = None
    event_time: str = ""
    location: str = ""
    organizer: str = ""
    style_preferences: list[NonEmptyText] = Field(default_factory=list, max_length=8)
    color_preferences: list[NonEmptyText] = Field(default_factory=list, max_length=8)
    visual_elements: list[NonEmptyText] = Field(default_factory=list, max_length=12)
    avoid_elements: list[NonEmptyText] = Field(default_factory=list, max_length=12)
    notes: str = Field(default="", max_length=2000)
    canvas: CanvasSize = Field(default_factory=lambda: CanvasSize(width=1080, height=1440))
    references: list[ReferenceSelection] = Field(default_factory=list, max_length=3)
    attention_priority: list[PriorityRole] = Field(default_factory=list, max_length=5)
    attention_layout: bool = True

    @field_validator("topic", "target_audience", "event_time", "location", "organizer", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        return "" if value is None else value.strip() if isinstance(value, str) else value

    @field_validator("subtitle", mode="before")
    @classmethod
    def normalize_subtitle(cls, value):
        return value.strip() or None if isinstance(value, str) else value

    @model_validator(mode="after")
    def unique_design_choices(self):
        self.topic = self.topic or self.title
        available = {"title", "main_visual"}
        if self.subtitle:
            available.add("subtitle")
        if self.event_time or self.location:
            available.add("event_info")
        if self.organizer:
            available.add("organizer")
        ids = [reference.case_id for reference in self.references]
        if len(ids) != len(set(ids)):
            raise ValueError("reference case ids must be unique")
        if len(self.attention_priority) != len(set(self.attention_priority)):
            raise ValueError("attention priorities must be unique")
        self.attention_priority = [role for role in self.attention_priority if role in available]
        return self
