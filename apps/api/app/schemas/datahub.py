"""Task evidence, subjective feedback and publication are distinct concepts."""

from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class HubModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CaseNotes(HubModel):
    title: str = Field(min_length=1, max_length=160)
    styles: list[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    ] = Field(default_factory=list, max_length=8)
    problem: str = Field(default="", max_length=1000)
    lesson: str = Field(default="", max_length=1600)
    applicable_when: str = Field(default="", max_length=800)
    avoid_when: str = Field(default="", max_length=800)
    rights: Literal["unconfirmed", "own_or_authorized"] = "unconfirmed"
    rights_note: str = Field(default="", max_length=500)


class UserFeedback(HubModel):
    verdict: Literal["unknown", "accepted", "rejected"] = "unknown"
    comment: str = Field(default="", max_length=1000)
    # Explicitly collected feedback; never inferred from 'finish' or a score.
    source: Literal["not_collected", "explicit_user", "demo_fixture"] = "not_collected"


class HubAudit(HubModel):
    revision: int
    action: str
    note: str
    snapshot: dict[str, Any] | None = None
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HubCase(HubModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    round_number: int = Field(ge=0, le=3)
    revision: int = 1
    status: Literal["candidate", "approved", "rejected", "withdrawn"] = "candidate"
    origin: Literal["runtime", "offline_demo"] = "runtime"
    evidence_hash: str
    evidence: dict[str, Any]
    image_hash: str
    before_image_hash: str | None = None
    notes: CaseNotes
    feedback: UserFeedback = Field(default_factory=UserFeedback)
    audit: list[HubAudit] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EditCaseRequest(HubModel):
    expected_revision: int = Field(ge=1, strict=True)
    notes: CaseNotes
    feedback: UserFeedback


class ReviewCaseRequest(HubModel):
    expected_revision: int = Field(ge=1, strict=True)
    action: Literal["approve", "reject", "withdraw"]
    note: str = Field(min_length=1, max_length=1000)


class ExperienceQuery(HubModel):
    query: str = Field(min_length=1, max_length=1000)
    poster_type: Literal["campus_lecture", "cultural_event", "club_recruitment"]
    exclude_run_id: UUID | None = None
    limit: int = Field(default=3, ge=1, le=3)
    include_demo: bool = False
