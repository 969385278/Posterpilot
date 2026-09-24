from langgraph.types import interrupt

from app.agent.state import PosterAgentState
from app.schemas.design_control import BackgroundTreatment, DesignControls
from app.poster.design_guards import assert_design_constraints, assert_rendered_locks, validate_control_targets
from app.schemas.react import (
    HumanCheckpoint,
    HumanDecision,
    KnowledgeCitationSummary,
)


def human_review(state: PosterAgentState) -> dict[str, object]:
    """Pause the graph and convert the resumed value into the next round state."""
    checkpoint = build_human_checkpoint(state)
    resumed = interrupt(checkpoint.model_dump(mode="json"))
    decision = HumanDecision.model_validate(resumed)
    if decision.action == "finish":
        return {
            "human_decision": decision,
            "pending_human": None,
        }
    prior_controls = state.get("design_controls") or DesignControls()
    controls = decision.controls or prior_controls.model_copy(update={
        "selected_candidate_id": None, "fact_edits": [],
        "adjustments": [item for item in prior_controls.adjustments if item.direction == "preserve"],
    })
    layout = state["layout"] or state["design_spec"].layout
    from app.poster.fact_edits import bind_instruction_edits
    controls = bind_instruction_edits(controls, decision.instruction, layout)
    validate_control_targets(controls, layout)
    selected_layout = layout
    if controls.selected_candidate_id:
        selected = next((item for item in state.get("layout_candidates", []) if item.id == controls.selected_candidate_id), None)
        if selected is None or not selected.selectable or selected.round_number != len(state["round_snapshots"]):
            raise ValueError("排版候选不存在、不可选或已过期，请刷新后选择")
        assert_design_constraints(layout, selected.layout, controls)
        if state.get("analysis_current"):
            assert_rendered_locks(state["analysis_current"], selected.analysis, controls)
        selected_layout = selected.layout.model_copy(deep=True)
    if controls.fact_edits:
        from app.poster.fact_edits import edited_layout
        selected_layout = edited_layout(selected_layout, controls.fact_edits)
        assert_design_constraints(layout, selected_layout, controls)
    return {
        "human_decision": decision,
        "human_instruction": (
            decision.instruction
            if decision.action == "instruct" and decision.instruction
            else "按用户选定特点、候选与保留条件修改" if controls.has_request else "按当前评测的主要问题自主优化"
        ),
        "round_number": len(state["round_snapshots"]) + 1,
        "tool_calls_in_round": 0,
        "tool_traces": [],
        "react_decision": None,
        "pending_human": None,
        "design_controls": controls,
        "layout": selected_layout,
        "round_base_layout": layout.model_copy(deep=True),
        "round_base_treatment": (state.get("background_treatment") or BackgroundTreatment()).model_copy(deep=True),
        "analysis_before_round": state.get("analysis_current"),
        "goal_verification": None,
        "round_rejection_reason": None,
    }


def route_human_decision(state: PosterAgentState) -> str:
    decision = state["human_decision"]
    if decision is None:
        raise ValueError("Human decision is missing after graph resume.")
    return "finalize" if decision.action == "finish" else "react_decide"


def route_after_round(state: PosterAgentState) -> str:
    return "finalize" if len(state["round_snapshots"]) >= 3 else "human_review"


def build_human_checkpoint(state: PosterAgentState) -> HumanCheckpoint:
    report = state["evaluation_optimized"] or state["evaluation_initial"]
    if report is None:
        raise ValueError("evaluation is required before requesting human input")
    citations = list(state["knowledge_citations"])
    if not citations and state["retrieval_generation"] is not None:
        citations = [
            KnowledgeCitationSummary(
                card_id=match.card.id,
                title=match.card.title,
                source_id=match.card.source_id,
                source_pages=match.card.source_pages,
            )
            for match in state["retrieval_generation"].matches
        ]
    issues = list(report.primary_issues)
    verification = state.get("goal_verification")
    analysis = state.get("analysis_current")
    checks = verification.checks if verification else analysis.readability_checks if analysis else []
    for check in checks:
        if check.status == "failed":
            issues.append(f"{check.label}：{check.detail}")
    issues = list(dict.fromkeys(issues))
    suggestion = (
        f"建议优先处理：{'；'.join(issues[:3])}。"
        if issues
        else "当前未发现明显问题，可结束任务或按主观偏好继续调整。"
    )
    return HumanCheckpoint(
        initial_attention_artifact=(
            state["evaluation_initial"].attention.heatmap_artifact
            if state["evaluation_initial"] is not None
            else None
        ),
        round_number=len(state["round_snapshots"]),
        score=report.scores.total,
        evaluation_notes=[
            f"可用评测权重：{report.scores.available_weight:g}/100；分数按可用信号归一化。",
            *(
                ["视觉评测不可用，当前分数未包含视觉模型判断。"]
                if report.vision.availability == "unavailable"
                else []
            ),
            *(
                ["注意力预测不可用，当前分数未包含 DeepGaze 信号。"]
                if report.attention.availability == "unavailable"
                else []
            ),
        ],
        primary_issues=issues,
        suggestion=suggestion,
        citations=citations,
        tool_traces=state["tool_traces"],
        poster_artifact=(
            state["round_snapshots"][-1].poster_artifact
            if state["round_snapshots"]
            else "poster_initial.png"
        ),
        attention_artifact=report.attention.heatmap_artifact,
        rounds=state["round_snapshots"],
        layout=(state["layout"] or state["design_spec"].layout).model_dump(mode="json") if state["design_spec"] is not None else None,
        analysis=state.get("analysis_current"),
        initial_analysis=state.get("analysis_initial"),
        controls=(state.get("design_controls") or DesignControls()).model_copy(update={"selected_candidate_id": None}),
        background_treatment=state.get("background_treatment") or BackgroundTreatment(),
        goal_verification=state.get("goal_verification"),
        layout_candidates=state.get("layout_candidates", []),
    )
