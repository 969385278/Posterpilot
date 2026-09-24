from app.agent.nodes.common import with_event
from app.agent.state import PosterAgentState
from app.agent.tools.react_tools import ReactToolRegistry
from app.schemas.react import ToolTrace
from app.schemas.design_control import BackgroundTreatment


async def execute_react_tool(
    state: PosterAgentState,
    *,
    tools: ReactToolRegistry,
) -> dict[str, object]:
    decision = state["react_decision"]
    design_spec = state["design_spec"]
    if decision is None or decision.tool_name is None or design_spec is None:
        raise ValueError("tool decision and design spec are required")
    layout = state["layout"] or design_spec.layout
    step = state["tool_calls_in_round"] + 1
    citations = list(state["knowledge_citations"])
    treatment = state.get("background_treatment") or BackgroundTreatment()
    publication = None
    try:
        result = await tools.execute(
            decision, layout=layout, controls=state.get("design_controls"),
            treatment=treatment, baseline_layout=state.get("round_base_layout"),
            baseline_treatment=state.get("round_base_treatment"),
        )
        updated_layout = result.layout
        treatment = result.treatment or treatment
        observation = result.observation
        citations.extend(result.citations)
        success = True
        publication = result.publication
        retrieval = result.retrieval or state["retrieval_optimization"]
    except Exception as error:
        updated_layout = layout
        observation = f"工具执行失败：{error}"
        success = False
        retrieval = state["retrieval_optimization"]
    trace = ToolTrace(
        round_number=state["round_number"],
        step=step,
        decision_summary=decision.summary,
        tool_name=decision.tool_name,
        tool_args=decision.arguments,
        observation=observation,
        success=success,
        tool_publication=publication,
        knowledge_card_ids=decision.knowledge_card_ids,
    )
    return {
        "layout": updated_layout,
        "background_treatment": treatment,
        "retrieval_optimization": retrieval,
        "knowledge_citations": _unique_citations(citations),
        "tool_calls_in_round": step,
        "tool_traces": [*state["tool_traces"], trace],
        "events": with_event(
            state,
            node=decision.tool_name,
            message=observation,
            payload={
                "round_number": state["round_number"],
                "step": step,
                "success": success,
                "tool_args": decision.arguments,
            },
        ),
    }


def _unique_citations(citations):
    unique = {}
    for citation in citations:
        unique[citation.card_id] = citation
    return list(unique.values())
