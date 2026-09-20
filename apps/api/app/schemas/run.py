from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.schemas.brief import NonEmptyText, PosterBrief

RunStatus = Literal["queued", "running", "waiting_for_human", "completed", "failed"]
RunEventType = Literal[
    "run_created",
    "node_started",
    "node_completed",
    "run_completed",
    "run_failed",
    "human_input_required",
    "human_input_received",
    "agent_decision",
    "tool_started",
    "tool_completed",
    "round_completed",
    "experience_captured",
    "experience_capture_pending",
]


class ArtifactReference(BaseModel):
    name: NonEmptyText
    relative_path: NonEmptyText
    media_type: NonEmptyText


class RunRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    status: RunStatus = "queued"
    brief: PosterBrief
    current_node: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    artifacts: list[ArtifactReference] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RunEvent(BaseModel):
    run_id: UUID
    type: RunEventType
    node: str | None = None
    message: NonEmptyText
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
