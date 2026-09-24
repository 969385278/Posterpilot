from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=1000)
    run_id: UUID | None = None
    conversation_id: UUID | None = None
    user_id: str = Field(default="local", pattern=r"^[A-Za-z0-9_-]{1,80}$")
    use_user_memory: bool = False


class AssistantCitation(BaseModel):
    id: str
    title: str
    source: str
    excerpt: str


class AssistantTrace(BaseModel):
    tool: str
    summary: str
    success: bool


class ModificationProposal(BaseModel):
    scope: Literal["typography", "layout", "background"]
    instruction: str = Field(min_length=1, max_length=1000)


class AssistantAnswer(BaseModel):
    id: UUID
    conversation_id: UUID
    question: str
    answer: str
    citations: list[AssistantCitation] = Field(default_factory=list)
    trace: list[AssistantTrace] = Field(default_factory=list)
    proposal: ModificationProposal | None = None
    run_id: UUID | None = None
    round_number: int | None = None
    degraded: bool = False
    degradation_reason: Literal[
        "model_unavailable", "model_timeout", "invalid_model_response",
        "model_request_failed", "tool_budget_exhausted", "invalid_citation",
    ] | None = None
    user_id: str = "local"
    memory_source_id: UUID | None = None


class AssistantStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["tool", "answer"]
    tool: (
        Literal[
            "search_knowledge", "search_cases", "inspect_poster", "analyze_image", "read_history",
            "read_user_profile", "read_memory_events", "search_visual_assets"
        ]
        | None
    ) = None
    query: str = Field(default="", max_length=1000)
    answer: str = Field(default="", max_length=6000)
    citation_ids: list[str] = Field(default_factory=list, max_length=12)
    proposal: ModificationProposal | None = None
