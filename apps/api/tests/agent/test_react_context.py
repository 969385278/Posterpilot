import json

from app.agent.prompts.react import build_react_messages
from app.rag.models import RetrievalResult
from tests.agent.test_react_tools import FakeRetriever
from app.rag.models import RetrievalRequest


def _payload(retrieval):
    messages = build_react_messages(
        human_instruction="增强标题", primary_issues=[], layout={},
        recent_traces=[], retrieval=retrieval,
    )
    return json.loads(messages[1]["content"])["retrieved_design_knowledge"]


async def test_knowledge_context_bounds_content_without_mutating_retrieval():
    retrieval = await FakeRetriever().retrieve(
        RetrievalRequest(intent="optimization", query="标题")
    )
    card = retrieval.matches[0].card
    card.content = "长正文" * 1000
    card.source_url = "https://example.com/design"
    card.source_locator = "Heading hierarchy"
    card.constraints = ["保留用户标题"]
    retrieval.matches = retrieval.matches * 4
    context = _payload(retrieval)
    assert len(context["cards"]) == 3
    first = context["cards"][0]
    assert len(first["content"]) == 1600
    assert first["content_truncated"] is True
    assert first["constraints"] == ["保留用户标题"]
    assert first["source_url"] == "https://example.com/design"
    assert first["source_locator"] == "Heading hierarchy"
    assert len(card.content) == 3000
    assert len(retrieval.matches) == 4


def test_empty_retrieval_exposes_fallback_without_invented_rules():
    context = _payload(RetrievalResult(query="标题", fallback_reason="low_similarity"))
    assert context == {"cards": [], "fallback_reason": "low_similarity"}
    assert _payload(None)["cards"] == []
