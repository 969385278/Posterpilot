from app.agent.nodes.common import with_event
from app.agent.nodes.retrieve_knowledge import Retriever
from app.agent.state import PosterAgentState
from app.rag.models import RetrievalRequest


async def retrieve_optimization_knowledge(
    state: PosterAgentState,
    *,
    retriever: Retriever,
) -> dict[str, object]:
    report = state["evaluation_initial"]
    if report is None:
        raise ValueError("initial evaluation is required before optimization retrieval")
    query = "\n".join(report.primary_issues) or state["brief"].topic
    result = await retriever.retrieve(
        RetrievalRequest(
            intent="optimization",
            query=query,
            target_roles=["title", "event_info", "main_visual"],
        )
    )
    return {
        "retrieval_optimization": result,
        "events": with_event(
            state,
            node="retrieve_optimization_knowledge",
            message="已检索优化阶段设计知识。",
            payload={"match_count": len(result.matches), "fallback_reason": result.fallback_reason},
        ),
    }
