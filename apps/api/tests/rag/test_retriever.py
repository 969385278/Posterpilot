from collections.abc import Sequence

import pytest

from app.rag.models import KnowledgeCard, RetrievalRequest, VectorHit
from app.rag.retriever import KnowledgeRetriever


def make_card(
    card_id: str,
    *,
    status: str = "approved",
    intents: list[str] | None = None,
    target_roles: list[str] | None = None,
) -> KnowledgeCard:
    return KnowledgeCard.model_validate(
        {
            "id": card_id,
            "knowledge_type": "rule",
            "category": "visual_hierarchy",
            "title": "主标题应成为第一视觉焦点",
            "content": "标题的信息层级应高于正文。",
            "signals": ["标题与正文大小接近"],
            "actions": ["增大标题字号"],
            "constraints": ["不得删除活动信息"],
            "retrieval_aliases": ["标题不醒目", "第一视觉焦点"],
            "intents": intents or ["generation", "optimization"],
            "target_roles": target_roles or ["title"],
            "source_id": "nng-visual-design",
            "source_locator": "Visual hierarchy definition",
            "review_status": status,
            "confidence": 0.9,
        }
    )


class FakeRepository:
    def __init__(self, cards: list[KnowledgeCard]):
        self.cards = cards

    def list_cards(self) -> list[KnowledgeCard]:
        return self.cards


class FakeVectorStore:
    def __init__(self, hits: list[VectorHit] | None = None, error: Exception | None = None):
        self.hits = hits or []
        self.error = error
        self.candidate_ids: list[str] = []

    async def search(
        self,
        query: str,
        *,
        candidate_ids: Sequence[str],
        limit: int,
    ) -> list[VectorHit]:
        del query, limit
        self.candidate_ids = list(candidate_ids)
        if self.error:
            raise self.error
        return self.hits


@pytest.mark.asyncio
async def test_retriever_filters_metadata_before_vector_search() -> None:
    approved = make_card("approved-title")
    wrong_intent = make_card("evaluation-only", intents=["evaluation"])
    candidate = make_card("candidate-title", status="candidate")
    store = FakeVectorStore([VectorHit(id="approved-title", similarity=0.86)])
    retriever = KnowledgeRetriever(FakeRepository([approved, wrong_intent, candidate]), store)

    result = await retriever.retrieve(
        RetrievalRequest(
            intent="generation",
            query="标题需要成为第一视觉焦点",
            target_roles=["title"],
            top_k=3,
            min_similarity=0.5,
        )
    )

    assert store.candidate_ids == ["approved-title"]
    assert [match.card.id for match in result.matches] == ["approved-title"]


@pytest.mark.asyncio
async def test_retriever_drops_low_similarity_hits() -> None:
    card = make_card("approved-title")
    store = FakeVectorStore([VectorHit(id=card.id, similarity=0.32)])
    retriever = KnowledgeRetriever(FakeRepository([card]), store)

    result = await retriever.retrieve(
        RetrievalRequest(intent="optimization", query="标题不醒目", min_similarity=0.6)
    )

    assert result.matches == []
    assert result.fallback_reason == "below_similarity_threshold"


@pytest.mark.asyncio
async def test_retriever_accepts_practical_semantic_match_at_default_threshold() -> None:
    card = make_card("approved-title")
    store = FakeVectorStore([VectorHit(id=card.id, similarity=0.38)])
    retriever = KnowledgeRetriever(FakeRepository([card]), store)

    result = await retriever.retrieve(
        RetrievalRequest(intent="optimization", query="活动信息需要更醒目")
    )

    assert [match.card.id for match in result.matches] == ["approved-title"]


@pytest.mark.asyncio
async def test_retriever_maps_event_info_to_legacy_time_venue_role() -> None:
    card = make_card("time-venue-rule", target_roles=["time_venue"])
    store = FakeVectorStore([VectorHit(id=card.id, similarity=0.8)])
    retriever = KnowledgeRetriever(FakeRepository([card]), store)

    await retriever.retrieve(
        RetrievalRequest(
            intent="optimization",
            query="时间地点需要组合展示",
            target_roles=["event_info"],
        )
    )

    assert store.candidate_ids == ["time-venue-rule"]


@pytest.mark.asyncio
async def test_retriever_fails_open_when_vector_store_is_unavailable() -> None:
    card = make_card("approved-title")
    store = FakeVectorStore(error=ConnectionError("chroma offline"))
    retriever = KnowledgeRetriever(FakeRepository([card]), store)

    result = await retriever.retrieve(RetrievalRequest(intent="generation", query="标题视觉层级"))

    assert result.matches == []
    assert result.fallback_reason == "vector_store_unavailable"
    assert result.error == "chroma offline"


@pytest.mark.parametrize("include_candidates", [False, True])
async def test_rejected_knowledge_never_enters_retrieval(include_candidates):
    cards = [
        make_card("approved"),
        make_card("candidate", status="candidate"),
        make_card("rejected", status="rejected"),
    ]
    # Deliberately return every ID: post-filtering must also defend against
    # an index that ignores the candidate constraint or has stale metadata.
    store = FakeVectorStore([VectorHit(id=card.id, similarity=0.99) for card in cards])
    result = await KnowledgeRetriever(FakeRepository(cards), store).retrieve(
        RetrievalRequest(
            intent="optimization", query="标题", include_candidates=include_candidates
        ),
    )
    expected = {"approved", "candidate"} if include_candidates else {"approved"}
    assert set(store.candidate_ids) == expected
    assert {match.card.id for match in result.matches} == expected
