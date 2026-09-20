from app.agent.nodes.common import with_event
from app.agent.prompts.react import build_react_messages
from app.agent.state import PosterAgentState
from app.providers.llm.base import JsonChatProvider
from app.schemas.react import ReactDecision
from app.agent.experience_context import retrieve_experience


async def react_decide(
    state: PosterAgentState,
    *,
    text_provider: JsonChatProvider,
    experience_source=None,
) -> dict[str, object]:
    experiences = retrieve_experience(state, experience_source, optimization=True)
    controls = state.get("design_controls")
    human = state.get("human_decision")
    selection_only = (controls and controls.selected_candidate_id and human and not human.instruction
                      and not any(goal.direction != "preserve" for goal in controls.adjustments))
    if selection_only:
        decision = ReactDecision(decision="finish_round", summary="采用用户明确选择的排版，不追加未经要求的修改，进入统一渲染与验证。")
    elif state["tool_calls_in_round"] >= 3:
        decision = ReactDecision(
            decision="finish_round",
            summary="本轮已达到三个工具调用的安全上限，进入统一复评。",
        )
    else:
        report = state["evaluation_optimized"] or state["evaluation_initial"]
        design_spec = state["design_spec"]
        if report is None or design_spec is None:
            raise ValueError("evaluation and design spec are required for ReAct decisions")
        layout = state["layout"] or design_spec.layout
        payload = await text_provider.complete_json(
            build_react_messages(
                human_instruction=state["human_instruction"],
                primary_issues=list(report.primary_issues),
                layout=layout.model_dump(mode="json"),
                recent_traces=state["tool_traces"],
                retrieval=state.get("retrieval_optimization"),
                controls=state["design_controls"].model_dump(mode="json") if state.get("design_controls") else None,
                analysis=state["analysis_current"].model_dump(mode="json") if state.get("analysis_current") else None,
                background_treatment=state["background_treatment"].model_dump(mode="json") if state.get("background_treatment") else None,
                selected_cases=state.get("selected_case_context", []),
                experiences=experiences,
            )
        )
        decision = ReactDecision.model_validate(payload)
    return {
        "react_decision": decision,
        "experience_references": experiences,
        "events": with_event(
            state,
            node="react_decide",
            message=decision.summary,
            payload={
                "decision": decision.decision,
                "tool_name": decision.tool_name,
                "round_number": state["round_number"],
                "experience_candidates": experiences,
                "experience_note": "参考候选，不代表已采纳；当前用户要求和锁定条件优先。",
            },
        ),
    }


def route_react_decision(state: PosterAgentState) -> str:
    decision = state["react_decision"]
    if decision is None:
        raise ValueError("ReAct decision is missing")
    return "finish_round" if decision.decision == "finish_round" else "execute_react_tool"
