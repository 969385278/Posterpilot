import asyncio
import threading

import pytest

from app.rag import lazy_chroma_store
from app.rag.lazy_chroma_store import LazyRemoteChromaStore
from app.rag.models import RetrievalRequest
from app.rag.retriever import KnowledgeRetriever
from tests.rag.test_chroma_store import FakeChroma
from tests.rag.test_retriever import FakeRepository, make_card


def store():
    return LazyRemoteChromaStore(
        chroma_url="http://127.0.0.1:8000",
        collection_name="test",
        embedding_function=None,
    )


async def search(subject):
    return await subject.search("标题层级", candidate_ids=["title-rule"], limit=3)


async def test_no_connection_on_construction_or_empty_query_and_failure_is_retryable(monkeypatch):
    calls = []

    def connect(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise ConnectionError("Chroma offline")
        return FakeChroma()

    monkeypatch.setattr(lazy_chroma_store, "create_remote_chroma", connect)
    subject = store()
    assert calls == []
    assert await subject.search("empty", candidate_ids=[], limit=3) == []
    assert calls == []
    with pytest.raises(ConnectionError):
        await search(subject)
    assert [item.id for item in await search(subject)] == ["title-rule"]
    assert [item.id for item in await search(subject)] == ["title-rule"]
    assert len(calls) == 2


async def test_concurrent_requests_and_cancelled_waiter_share_initialization(monkeypatch):
    started, release = threading.Event(), threading.Event()
    calls = []

    def connect(**kwargs):
        calls.append(kwargs)
        started.set()
        assert release.wait(5)
        return FakeChroma()

    monkeypatch.setattr(lazy_chroma_store, "create_remote_chroma", connect)
    subject = store()
    first = asyncio.create_task(search(subject))
    try:
        assert await asyncio.to_thread(started.wait, 2)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        second = asyncio.create_task(search(subject))
        third = asyncio.create_task(search(subject))
        release.set()
        results = await asyncio.gather(second, third)
        assert all(result[0].id == "title-rule" for result in results)
        assert len(calls) == 1
    finally:
        release.set()


async def test_failed_query_reconnects_instead_of_caching_stale_collection(monkeypatch):
    calls = []

    class StaleChroma:
        async def asimilarity_search_with_relevance_scores(self, *args, **kwargs):
            raise ConnectionError("collection unavailable after server restart")

    def connect(**kwargs):
        calls.append(kwargs)
        return StaleChroma() if len(calls) == 1 else FakeChroma()

    monkeypatch.setattr(lazy_chroma_store, "create_remote_chroma", connect)
    subject = store()
    with pytest.raises(ConnectionError):
        await search(subject)
    assert (await search(subject))[0].id == "title-rule"
    assert len(calls) == 2


def test_invalid_configuration_is_not_hidden_as_an_offline_service():
    with pytest.raises(ValueError, match="http or https"):
        LazyRemoteChromaStore(chroma_url="bad-url", collection_name="test", embedding_function=None)


async def test_retrieval_reports_outage_and_recovers_on_the_same_instance(monkeypatch):
    calls = []

    def connect(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise ConnectionError("Chroma offline")
        return FakeChroma()

    monkeypatch.setattr(lazy_chroma_store, "create_remote_chroma", connect)
    retriever = KnowledgeRetriever(FakeRepository([make_card("title-rule")]), store())
    request = RetrievalRequest(intent="generation", query="标题视觉层级")
    unavailable = await retriever.retrieve(request)
    assert unavailable.matches == []
    assert unavailable.candidate_ids == ["title-rule"]
    assert unavailable.fallback_reason == "vector_store_unavailable"
    assert unavailable.error == "Chroma offline"
    recovered = await retriever.retrieve(request)
    assert recovered.fallback_reason is None
    assert recovered.error is None
    assert [match.card.id for match in recovered.matches] == ["title-rule"]
    assert len(calls) == 2
