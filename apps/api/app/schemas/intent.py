from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.brief import PosterBrief
from app.schemas.design_control import DesignControls

IntentLabel = Literal["generate", "modify", "question", "out_of_scope", "clarify"]


class IntentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=1000)
    run_id: UUID | None = None
    user_id: str = Field(default="local", pattern=r"^[A-Za-z0-9_-]{1,80}$")
    use_user_memory: bool = False


class Requirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: Literal["title", "subtitle", "event_info", "organizer", "main_visual", "background"]
    goal: str = Field(min_length=1, max_length=300)
    quote: str = Field(min_length=1, max_length=300)
    hard_constraint: bool = False


class IntentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: IntentLabel
    requirements: list[Requirement] = Field(default_factory=list, max_length=12)
    controls: DesignControls = Field(default_factory=DesignControls)
    brief: PosterBrief | None = None
    explanation: str = Field(default="", max_length=500)


class IntentResolution(IntentPlan):
    classifier: str
    classifier_confidence: float | None = Field(ge=0, le=1, allow_inf_nan=False)
    route_method: Literal["lightweight", "llm_fallback", "llm_direct", "unavailable"]
    fallback_used: bool
    needs_confirmation: bool = True
    can_apply: bool = False
    warnings: list[str] = Field(default_factory=list)
    profile_revision: int | None = None
    round_number: int | None = None
