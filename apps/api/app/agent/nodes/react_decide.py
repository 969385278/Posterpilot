from app.agent.nodes.common import with_event
from app.agent.prompts.react import build_react_messages
from app.agent.state import PosterAgentState
from app.providers.llm.base import JsonChatProvider
from app.schemas.react import ReactDecision
from app.agent.experience_context import retrieve_decision_cards, retrieve_experience


def _operation(value):
    """Reason wording does not make an otherwise identical mutation new."""
    if isinstance(value, dict):
        return {k: _operation(v) for k, v in value.items() if k not in {"reason", "source_rule_ids"}}
    if isinstance(value, list):
        return [_operation(v) for v in value]
    return value


async def react_decide(
    state: PosterAgentState,
    *,
    text_provider: JsonChatProvider,
    experience_source=None,
    tool_catalog: list[dict] | None = None,
) -> dict[str, object]:
    experiences = retrieve_experience(state, experience_source, optimization=True)
    decision_cards = retrieve_decision_cards(state, experience_source, tool_catalog=tool_catalog)
    controls = state.get("design_controls")
    human = state.get("human_decision")
    selection_only = (controls and controls.selected_candidate_id and human and not human.instruction
                      and not controls.element_goals
                      and not any(goal.direction != "preserve" for goal in controls.adjustments))
    fact_only = (controls and controls.fact_edits and not controls.element_goals
                 and not any(goal.direction != "preserve" for goal in controls.adjustments))
    if fact_only:
        decision = ReactDecision(decision="finish_round", summary="已应用用户确认的文字字段替换，进入渲染、事实与保护条件验收。")
    elif selection_only:
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
                # After mutations this measurement describes an obsolete image.
                # Current layout and observations are the only fresh evidence until render.
                analysis=(state["analysis_current"].model_dump(mode="json")
                          if state.get("analysis_current") and not any(t.success and t.tool_name in {
                              "modify_typography", "modify_layout", "adjust_background",
                              "set_text_opacity", "align_text_group"} for t in state["tool_traces"]) else None),
                background_treatment=state["background_treatment"].model_dump(mode="json") if state.get("background_treatment") else None,
                selected_cases=state.get("selected_case_context", []),
                experiences=experiences,
                user_context=state.get("user_context"),
                decision_cards=decision_cards,
                tool_catalog=tool_catalog,
            )
        )
        decision = ReactDecision.model_validate(payload)
        if decision.decision == "tool_call" and any(
            trace.success and trace.tool_name == decision.tool_name
            and _operation(trace.tool_args) == _operation(decision.arguments) for trace in state["tool_traces"]
        ):
            decision = ReactDecision(decision="finish_round", summary="相同工具参数已执行，停止重复动作并进入统一渲染验收。")
    return {
        "react_decision": decision,
        "experience_references": experiences,
        "decision_card_references": decision_cards,
        "tool_catalog": tool_catalog or [],
        "events": with_event(
            state,
            node="react_decide",
            message=decision.summary,
            payload={
                "decision": decision.decision,
                "tool_name": decision.tool_name,
                "round_number": state["round_number"],
                "experience_candidates": experiences,
                "decision_card_candidates": decision_cards,
                "experience_note": "参考候选，不代表已采纳；当前用户要求和锁定条件优先。",
            },
        ),
    }


def route_react_decision(state: PosterAgentState) -> str:
    decision = state["react_decision"]
    if decision is None:
        raise ValueError("ReAct decision is missing")
    return "finish_round" if decision.decision == "finish_round" else "execute_react_tool"
