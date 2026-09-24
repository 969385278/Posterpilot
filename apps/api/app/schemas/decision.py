from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import Field, StringConstraints, model_validator

from app.schemas.brief import PosterType
from app.schemas.datahub import HubAudit, HubModel
from app.schemas.layout import ElementRole

DecisionTool = Literal[
    "search_design_knowledge",
    "search_poster_cases",
    "modify_typography",
    "modify_layout",
    "adjust_background",
    "set_text_opacity",
    "align_text_group",
]
PolicyTerm = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class DecisionPolicy(HubModel):
    title: str = Field(min_length=1, max_length=160)
    problem: str = Field(min_length=1, max_length=500)
    applicable_when: str = Field(min_length=1, max_length=800)
    avoid_when: str = Field(min_length=1, max_length=800)
    poster_types: list[PosterType] = Field(min_length=1, max_length=3)
    required_roles: list[ElementRole] = Field(default_factory=list, max_length=9)
    trigger_terms: list[PolicyTerm] = Field(min_length=1, max_length=12)
    excluded_terms: list[PolicyTerm] = Field(default_factory=list, max_length=12)
    candidate_tools: list[DecisionTool] = Field(min_length=1, max_length=5)
    verification_rules: list[Literal["goals_met", "locks_preserved", "no_critical_rules"]] = Field(
        default_factory=lambda: ["goals_met", "locks_preserved", "no_critical_rules"],
        min_length=1,
        max_length=3,
    )

    @model_validator(mode="after")
    def unique_policy_values(self):
        for name in (
            "poster_types",
            "required_roles",
            "trigger_terms",
            "excluded_terms",
            "candidate_tools",
            "verification_rules",
        ):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must not contain duplicates")
        return self


class CreateDecisionCard(HubModel):
    source_case_id: UUID
    policy: DecisionPolicy


class EditDecisionCard(HubModel):
    expected_revision: int = Field(ge=1)
    policy: DecisionPolicy


class DecisionCard(HubModel):
    id: UUID = Field(default_factory=uuid4)
    revision: int = 1
    status: Literal["candidate", "approved", "rejected", "withdrawn"] = "candidate"
    source_case_id: UUID
    source_revision: int
    evidence_hash: str
    source_run_id: UUID
    origin: Literal["runtime", "offline_demo"]
    policy: DecisionPolicy
    audit: list[HubAudit] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
