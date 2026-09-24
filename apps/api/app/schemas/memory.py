from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.title_font import normalize_title_font

MemoryKey = Literal["style", "color", "title_font", "target_audience", "avoid_elements"]
MemoryScope = Literal["all", "campus_lecture", "cultural_event", "club_recruitment"]


class MemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceMessageInput(MemoryInput):
    id: UUID
    text: str = Field(min_length=1, max_length=6000)
    conversation_id: UUID | None = None
    run_id: UUID | None = None


class MemoryEventInput(MemoryInput):
    source_id: UUID
    quote: str = Field(min_length=1, max_length=1000)
    key: MemoryKey
    value: str = Field(min_length=1, max_length=300)
    scope: MemoryScope = "all"
    kind: Literal["explicit", "temporary", "weak"]
    confirmed: bool = False
    expected_revision: int = Field(ge=0)

    @model_validator(mode="after")
    def require_confirmation(self):
        if self.kind == "explicit" and not self.confirmed:
            raise ValueError("长期画像更新必须由用户明确确认")
        if self.key == "title_font":
            self.value = normalize_title_font(self.value)
        return self


class RetractMemoryInput(MemoryInput):
    expected_revision: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=500)


class MemorySuggestion(MemoryInput):
    quote: str = Field(min_length=1, max_length=1000)
    key: MemoryKey
    value: str = Field(min_length=1, max_length=300)
    scope: MemoryScope = "all"
    kind: Literal["explicit", "temporary", "weak"]

    @model_validator(mode="after")
    def validate_font(self):
        if self.key == "title_font":
            self.value = normalize_title_font(self.value)
        return self


class MemoryExtraction(MemoryInput):
    suggestions: list[MemorySuggestion] = Field(default_factory=list, max_length=8)
