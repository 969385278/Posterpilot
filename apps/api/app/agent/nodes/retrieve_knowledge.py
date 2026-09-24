from typing import Protocol

from app.agent.nodes.common import with_event
from app.agent.state import PosterAgentState
from app.rag.models import RetrievalRequest, RetrievalResult
from app.rag.case_repository import CaseRepository
from app.agent.user_context import personalized_brief


class Retriever(Protocol):
    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult: ...


async def retrieve_generation_knowledge(
    state: PosterAgentState,
    *,
    retriever: Retriever,
) -> dict[str, object]:
    brief = personalized_brief(state["brief"], state.get("user_context"))
    selected_cases = CaseRepository().resolve_selections(brief.references)
    query_parts = [brief.topic, " ".join(brief.style_preferences), " ".join(brief.visual_elements)]
    query_parts.extend(" ".join(case["selected_features"].values()) for case in selected_cases)
    query = "\n".join(query_parts)
    request = RetrievalRequest(
        intent="generation",
        query=query,
        target_roles=["title", "main_visual", "event_info"],
    )
    result = await retriever.retrieve(request)
    return {
        "retrieval_generation": result,
        "selected_case_context": selected_cases,
        "events": with_event(
            state,
            node="retrieve_generation_knowledge",
            message="已检索生成阶段设计知识。",
            payload={"match_count": len(result.matches), "fallback_reason": result.fallback_reason},
        ),
    }
