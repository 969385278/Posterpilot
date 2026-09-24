from pathlib import Path
import re

from app.agent.nodes.common import with_event
from app.agent.state import PosterAgentState
from app.poster.renderer import PosterRenderer
from app.schemas.react import RoundSnapshot
from app.schemas.evaluation import EvaluationReport
from app.evaluation.comparison import compare_reports
from app.schemas.design_control import BackgroundTreatment, DesignControls
from app.poster.design_guards import DesignConstraintError, assert_design_constraints, assert_rendered_locks
from app.evaluation.design_analysis import analyze_design


def render_round(
    state: PosterAgentState,
    *,
    renderer: PosterRenderer,
    run_directory: Path | str,
) -> dict[str, object]:
    design_spec = state["design_spec"]
    main_visual_path = state["main_visual_path"]
    if design_spec is None or not main_visual_path:
        raise ValueError("design spec and main visual are required to render a ReAct round")
    layout = state["layout"] or design_spec.layout
    name = f"poster_round_{state['round_number']}.png"
    treatment = state.get("background_treatment") or BackgroundTreatment()
    controls = state.get("design_controls") or DesignControls()
    base = state.get("round_base_layout") or layout
    base_treatment = state.get("round_base_treatment") or treatment
    assert_design_constraints(base, layout, controls, before_treatment=base_treatment, after_treatment=treatment)
    result = renderer.render(
        layout,
        main_visual_path=main_visual_path,
        output_path=Path(run_directory) / name,
        background_color=design_spec.palette.background,
        treatment=treatment,
    )
    # Repair sampled contrast after an explicit opacity edit, without changing the
    # requested opacity, position, or any locked/explicitly requested text color.
    opacity_ids = {goal.element_id for goal in controls.element_goals if goal.kind == "opacity"}
    color_changes = []
    if opacity_ids and not re.search(r"颜色|色值|#[0-9a-fA-F]{6}", state.get("human_instruction", "")):
        from app.poster.initial_text_colors import _adapt_colors_for_background
        from app.schemas.design_control import ElementLock
        locked = {lock.element_id: lock for lock in controls.locks}
        for element in layout.elements:
            if element.content and element.id not in opacity_ids:
                locked[element.id] = ElementLock(element_id=element.id, properties=["typography"])
        adapted, color_changes = _adapt_colors_for_background(
            layout, palette=design_spec.palette, main_visual_path=main_visual_path,
            treatment=treatment, text_facts=result.text_facts,
            controls=controls.model_copy(update={"locks": list(locked.values())}),
        )
        if color_changes:
            assert_design_constraints(base, adapted, controls, before_treatment=base_treatment, after_treatment=treatment)
            layout = adapted
            result = renderer.render(layout, main_visual_path=main_visual_path,
                output_path=Path(run_directory) / name, background_color=design_spec.palette.background,
                treatment=treatment)
    rejection_reason = None
    if state.get("analysis_before_round"):
        measured = analyze_design(layout, main_visual_path=main_visual_path, treatment=treatment, text_facts=result.text_facts)
        try:
            assert_rendered_locks(state["analysis_before_round"], measured, controls)
        except DesignConstraintError as error:
            rejection_reason = str(error)
            layout, treatment = base.model_copy(deep=True), base_treatment.model_copy(deep=True)
            result = renderer.render(layout, main_visual_path=main_visual_path, output_path=Path(run_directory) / name, background_color=design_spec.palette.background, treatment=treatment)
    return {
        "poster_optimized_path": str(result.path),
        "layout": layout,
        "background_treatment": treatment,
        "round_rejection_reason": rejection_reason,
        "rendered_text_facts": result.text_facts,
        "events": with_event(
            state,
            node="render_round",
            message=f"第 {state['round_number']} 轮触发渲染保护，已保留本轮开始的版本：{rejection_reason}" if rejection_reason else f"已渲染第 {state['round_number']} 轮海报。",
            payload={"round_number": state["round_number"], "artifact": name,
                     "opacity_readability_color_adjustments": color_changes},
        ),
    }


def complete_round(state: PosterAgentState) -> dict[str, object]:
    report = state["evaluation_optimized"]
    poster_path = state["poster_optimized_path"]
    if report is None or not poster_path:
        raise ValueError("round poster and evaluation are required")
    previous_report = (
        EvaluationReport.model_validate(state["round_snapshots"][-1].evaluation)
        if state["round_snapshots"]
        else state["evaluation_initial"]
    )
    comparison = compare_reports(previous_report, report)
    artifact = Path(poster_path).name
    snapshot = RoundSnapshot(
        round_number=state["round_number"],
        poster_artifact=artifact,
        attention_artifact=report.attention.heatmap_artifact,
        score=report.scores.total,
        score_delta=comparison.delta,
        comparison_reason=comparison.reason,
        evaluation=report.model_dump(mode="json"),
        tool_traces=state["tool_traces"],
        analysis=state.get("analysis_current"),
        controls=state.get("design_controls") or DesignControls(),
        background_treatment=state.get("background_treatment") or BackgroundTreatment(),
        goal_verification=state.get("goal_verification"),
    )
    return {
        "round_snapshots": [*state["round_snapshots"], snapshot],
        "iteration": state["round_number"],
        "events": with_event(
            state,
            node="complete_round",
            message=f"第 {state['round_number']} 轮优化与复评已完成。",
            payload={
                "round_number": state["round_number"],
                "score": snapshot.score,
                "score_delta": snapshot.score_delta,
            },
        ),
    }
