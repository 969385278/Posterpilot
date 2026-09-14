from collections.abc import Sequence

import pytest
from langchain_core.documents import Document

from app.rag.langchain_chroma_store import ChromaVectorStore


class FakeChroma:
    def __init__(self):
        self.query = ""
        self.k = 0
        self.filter: dict[str, object] = {}

    async def asimilarity_search_with_relevance_scores(
        self,
        query: str,
        *,
        k: int,
        filter: dict[str, object],
    ) -> list[tuple[Document, float]]:
        self.query = query
        self.k = k
        self.filter = filter
        return [
            (Document(page_content="rule", metadata={"card_id": "title-rule"}), 0.84),
            (Document(page_content="stale", metadata={"card_id": "not-a-candidate"}), 0.99),
        ]


@pytest.mark.asyncio
async def test_chroma_search_limits_query_to_candidate_ids() -> None:
    chroma = FakeChroma()
    store = ChromaVectorStore(chroma)

    hits = await store.search(
        "标题视觉层级",
        candidate_ids=["title-rule", "contrast-rule"],
        limit=4,
    )

    assert chroma.filter == {"card_id": {"$in": ["title-rule", "contrast-rule"]}}
    assert [hit.id for hit in hits] == ["title-rule"]
    assert hits[0].similarity == 0.84


class FakeIndexStore:
    def __init__(self):
        self.reset_calls = 0
        self.documents: Sequence[Document] = []
        self.ids: Sequence[str] = []

    def reset_collection(self) -> None:
        self.reset_calls += 1

    def add_documents(self, documents: Sequence[Document], *, ids: Sequence[str]) -> None:
        self.documents = documents
        self.ids = ids


def test_index_rebuild_creates_one_document_per_approved_card(approved_card) -> None:
    from app.rag.indexer import KnowledgeIndexer

    store = FakeIndexStore()
    indexer = KnowledgeIndexer(store)

    count = indexer.rebuild([approved_card])

    assert count == 1
    assert store.reset_calls == 1
    assert list(store.ids) == [approved_card.id]
    assert store.documents[0].metadata["card_id"] == approved_card.id
    assert approved_card.actions[0] in store.documents[0].page_content

