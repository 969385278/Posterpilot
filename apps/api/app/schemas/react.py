from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.brief import NonEmptyText
from app.schemas.design_control import BackgroundTreatment, DesignControls, GoalVerification, PosterAnalysis
from app.schemas.layout_candidate import LayoutCandidate

ReactToolName = Literal[
    "search_design_knowledge",
    "search_poster_cases",
    "modify_typography",
    "modify_layout",
    "modify_visual",
    "adjust_background",
    "set_text_opacity",
    "align_text_group",
    "finish_round",
]
HumanDecisionAction = Literal["approve", "instruct", "finish"]
ReactDecisionType = Literal["tool_call", "finish_round"]


class HumanDecision(BaseModel):
    action: HumanDecisionAction
    instruction: str | None = Field(default=None, max_length=1000)
    controls: DesignControls | None = None

    @model_validator(mode="after")
    def validate_instruction(self) -> "HumanDecision":
        if self.action == "instruct":
            if (not self.instruction or not self.instruction.strip()) and not (self.controls and self.controls.has_request):
                raise ValueError("instruction is required when action is instruct")
            self.instruction = self.instruction.strip() if self.instruction else None
        elif self.instruction is not None:
            raise ValueError("instruction is only allowed when action is instruct")
        if self.action == "finish" and self.controls is not None:
            raise ValueError("finish cannot change design controls")
        return self


class HumanDecisionRequest(HumanDecision):
    # Transport precondition, not an instruction passed into the Agent.
    expected_round_number: int = Field(ge=0, le=3, strict=True)


class ReactDecision(BaseModel):
    decision: ReactDecisionType
    summary: NonEmptyText
    tool_name: ReactToolName | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    knowledge_card_ids: list[NonEmptyText] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_tool_choice(self) -> "ReactDecision":
        if self.decision == "tool_call":
            if self.tool_name is None or self.tool_name == "finish_round":
                raise ValueError("tool_call requires a modification or knowledge tool")
        elif self.tool_name is not None or self.arguments:
            raise ValueError("finish_round cannot include a tool call")
        return self


class KnowledgeCitationSummary(BaseModel):
    card_id: NonEmptyText
    title: NonEmptyText
    source_id: NonEmptyText
    source_pages: list[int] = Field(default_factory=list)


class ToolTrace(BaseModel):
    round_number: int = Field(ge=1, le=3)
    step: int = Field(ge=1, le=3)
    decision_summary: NonEmptyText
    tool_name: ReactToolName
    tool_args: dict[str, Any] = Field(default_factory=dict)
    observation: NonEmptyText
    success: bool
    tool_publication: dict[str, Any] | None = None
    knowledge_card_ids: list[NonEmptyText] = Field(default_factory=list)


class HumanCheckpoint(BaseModel):
    initial_attention_artifact: str | None = None
    round_number: int = Field(ge=0, le=3)
    score: float = Field(ge=0, le=100)
    evaluation_notes: list[str] = Field(default_factory=list)
    primary_issues: list[NonEmptyText] = Field(default_factory=list)
    suggestion: NonEmptyText
    citations: list[KnowledgeCitationSummary] = Field(default_factory=list)
    tool_traces: list[ToolTrace] = Field(default_factory=list)
    poster_artifact: str | None = None
    attention_artifact: str | None = None
    rounds: list["RoundSnapshot"] = Field(default_factory=list)
    layout: dict[str, Any] | None = None
    analysis: PosterAnalysis | None = None
    initial_analysis: PosterAnalysis | None = None
    controls: DesignControls = Field(default_factory=DesignControls)
    background_treatment: BackgroundTreatment = Field(default_factory=BackgroundTreatment)
    goal_verification: GoalVerification | None = None
    layout_candidates: list[LayoutCandidate] = Field(default_factory=list, max_length=3)


class RoundSnapshot(BaseModel):
    round_number: int = Field(ge=1, le=3)
    poster_artifact: NonEmptyText
    attention_artifact: str | None = None
    score: float = Field(ge=0, le=100)
    score_delta: float | None
    comparison_reason: str | None = None
    evaluation: dict[str, Any]
    tool_traces: list[ToolTrace] = Field(default_factory=list)
    analysis: PosterAnalysis | None = None
    controls: DesignControls = Field(default_factory=DesignControls)
    background_treatment: BackgroundTreatment = Field(default_factory=BackgroundTreatment)
    goal_verification: GoalVerification | None = None


class AgentExecutionOutcome(BaseModel):
    status: Literal["waiting_for_human", "completed"]
    checkpoint: HumanCheckpoint | None = None
    result: dict[str, Any] | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_matching_payload(self) -> "AgentExecutionOutcome":
        if self.status == "waiting_for_human" and self.checkpoint is None:
            raise ValueError("waiting outcome requires a checkpoint")
        if self.status == "completed" and self.result is None:
            raise ValueError("completed outcome requires a result")
        return self
