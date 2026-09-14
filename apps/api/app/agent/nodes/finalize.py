from app.agent.nodes.common import with_event
from app.agent.state import PosterAgentState
from app.evaluation.comparison import compare_reports


def finalize(state: PosterAgentState) -> dict[str, object]:
    initial = state["evaluation_initial"]
    optimized = state["evaluation_optimized"] or initial
    if initial is None:
        raise ValueError("initial evaluation is required before finalizing a run")
    comparison = compare_reports(initial, optimized)
    score_delta = comparison.delta
    outcome = comparison.outcome
    result = {
        "poster_initial_path": state["poster_initial_path"],
        "poster_optimized_path": state["poster_optimized_path"] or state["poster_initial_path"],
        "evaluation_initial": initial.model_dump(mode="json"),
        "evaluation_optimized": optimized.model_dump(mode="json"),
        "score_delta": score_delta,
        "outcome": outcome,
        "comparison_reason": comparison.reason,
        "rounds": [snapshot.model_dump(mode="json") for snapshot in state["round_snapshots"]],
        "tool_traces": [trace.model_dump(mode="json") for trace in state["tool_traces"]],
        "analysis_initial": state["analysis_initial"].model_dump(mode="json") if state.get("analysis_initial") else None,
        "analysis_current": state["analysis_current"].model_dump(mode="json") if state.get("analysis_current") else None,
        "goal_verification": state["goal_verification"].model_dump(mode="json") if state.get("goal_verification") else None,
        "design_controls": state["design_controls"].model_dump(mode="json") if state.get("design_controls") else {},
        "background_treatment": state["background_treatment"].model_dump(mode="json") if state.get("background_treatment") else {},
        "selected_case_references": state.get("selected_case_context", []),
    }
    return {
        "result": result,
        "events": with_event(
            state,
            node="finalize",
            message="已保存初版、轮次版本与真实复评结果。",
            payload={"score_delta": score_delta, "outcome": result["outcome"]},
        ),
    }
