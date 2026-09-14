from app.agent.nodes.common import with_event
from app.agent.prompts.optimization import build_optimization_messages
from app.agent.state import PosterAgentState
from app.poster.action_validator import validate_actions
from app.providers.llm.base import JsonChatProvider
from app.schemas.optimization import OptimizationPlan


async def plan_optimization(
    state: PosterAgentState,
    *,
    text_provider: JsonChatProvider,
) -> dict[str, object]:
    if state["iteration"] >= 1:
        raise ValueError("MVP only allows one optimization iteration")
    report = state["evaluation_initial"]
    design_spec = state["design_spec"]
    if report is None or design_spec is None:
        raise ValueError("initial evaluation and design spec are required before optimization")
    layout = state["layout"] or design_spec.layout
    issues_text = "\n".join(report.primary_issues) or "未发现可优化问题。"
    retrieval = state["retrieval_optimization"]
    knowledge_text = "\n\n".join(
        f"[{match.card.id}] {match.card.title}\n{match.card.content}"
        for match in retrieval.matches
    ) if retrieval else "优先修复硬规则和可读性问题。"
    payload = await text_provider.complete_json(
        build_optimization_messages(issues_text, knowledge_text=knowledge_text)
    )
    plan = OptimizationPlan.model_validate(payload)
    validate_actions(plan.actions, layout)
    return {
        "optimization_plan": plan,
        "events": with_event(
            state,
            node="plan_optimization",
            message="已生成并校验一轮优化计划。",
            payload={
                "action_count": len(plan.actions),
                "regenerate_visual": plan.regenerate_visual,
            },
        ),
    }
