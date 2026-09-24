from typing import Any, TypedDict

from app.schemas.brief import PosterBrief
from app.schemas.design_control import BackgroundTreatment, DesignControls, GoalVerification, PosterAnalysis, RenderedTextFact
from app.schemas.layout_candidate import LayoutCandidate
from app.schemas.react import (
    HumanCheckpoint,
    HumanDecision,
    KnowledgeCitationSummary,
    ReactDecision,
    RoundSnapshot,
    ToolTrace,
)


class PosterAgentState(TypedDict):
    brief: PosterBrief
    retrieval_generation: Any | None
    retrieval_optimization: Any | None
    design_spec: Any | None
    layout: Any | None
    main_visual_path: str | None
    poster_initial_path: str | None
    evaluation_initial: Any | None
    optimization_plan: Any | None
    poster_optimized_path: str | None
    evaluation_optimized: Any | None
    result: dict[str, Any] | None
    events: list[dict[str, Any]]
    errors: list[dict[str, str]]
    iteration: int
    run_id: str | None
    run_directory: str | None
    human_instruction: str
    round_number: int
    tool_calls_in_round: int
    react_decision: ReactDecision | None
    tool_traces: list[ToolTrace]
    round_snapshots: list[RoundSnapshot]
    knowledge_citations: list[KnowledgeCitationSummary]
    pending_human: HumanCheckpoint | None
    human_decision: HumanDecision | None
    design_controls: DesignControls
    background_treatment: BackgroundTreatment
    rendered_text_facts: list[RenderedTextFact]
    analysis_initial: PosterAnalysis | None
    analysis_current: PosterAnalysis | None
    analysis_before_round: PosterAnalysis | None
    round_base_layout: Any | None
    round_base_treatment: BackgroundTreatment | None
    goal_verification: GoalVerification | None
    layout_candidates: list[LayoutCandidate]
    round_rejection_reason: str | None
    selected_case_context: list[dict]
    experience_references: list[dict]
    user_context: dict
    decision_card_references: list[dict]
    tool_catalog: list[dict]
    visual_asset_retrieval: dict


def initial_agent_state(brief: PosterBrief) -> PosterAgentState:
    return PosterAgentState(
        brief=brief,
        retrieval_generation=None,
        retrieval_optimization=None,
        design_spec=None,
        layout=None,
        main_visual_path=None,
        poster_initial_path=None,
        evaluation_initial=None,
        optimization_plan=None,
        poster_optimized_path=None,
        evaluation_optimized=None,
        result=None,
        events=[],
        errors=[],
        iteration=0,
        run_id=None,
        run_directory=None,
        human_instruction="",
        round_number=0,
        tool_calls_in_round=0,
        react_decision=None,
        tool_traces=[],
        round_snapshots=[],
        knowledge_citations=[],
        pending_human=None,
        human_decision=None,
        design_controls=DesignControls(attention_priority=brief.attention_priority),
        background_treatment=BackgroundTreatment(),
        rendered_text_facts=[],
        analysis_initial=None,
        analysis_current=None,
        analysis_before_round=None,
        round_base_layout=None,
        round_base_treatment=None,
        goal_verification=None,
        layout_candidates=[],
        round_rejection_reason=None,
        selected_case_context=[],
        visual_asset_retrieval={},
        experience_references=[],
        user_context={},
        decision_card_references=[],
        tool_catalog=[],
    )
