import json

import pytest

from app.experiments.retrieval import compare_retrieval, retrieval_metrics
from app.rag.models import RetrievalCase, VectorHit
from tests.rag.test_retriever import FakeVectorStore, make_card


def test_recall_counts_all_relevant_documents_without_duplicate_credit():
    result = retrieval_metrics(["a", "b"], ["a", "a", "forbidden"], ["forbidden"])
    assert result["recall"] == 0.5
    assert result["hit_rate"] == 1
    assert result["reciprocal_rank"] == 1
    assert result["missing_relevant"] == ["b"]
    assert result["forbidden_hits"] == ["forbidden"]


async def test_paired_run_uses_one_vector_call_and_writes_raw_evidence(tmp_path):
    calls = []

    class Store:
        async def search(self, query, **kwargs):
            calls.append((query, kwargs))
            return [VectorHit(id="b", similarity=0.8), VectorHit(id="a", similarity=0.7)]

    cases = [
        RetrievalCase(
            id="query", intent="generation", query="标题层级", expected_card_ids=["a", "b"]
        )
    ]
    path = tmp_path / "rows.jsonl"
    summary, rows = await compare_retrieval(
        [make_card("a"), make_card("b")], cases, Store(), top_k=1, row_path=path
    )
    assert len(calls) == 1
    assert calls[0][1]["limit"] == 3
    assert summary["conditions"]["vector_only"]["macro_recall"] == 0.5
    assert summary["conditions"]["vector_only"]["hit_rate"] == 1
    assert rows[0]["conditions"]["vector_only"]["ranked_ids"] == ["b"]
    assert json.loads(path.read_text(encoding="utf-8"))["captured_hits"][0]["similarity"] == 0.8
    with pytest.raises(FileExistsError):
        await compare_retrieval([make_card("a"), make_card("b")], cases, Store(), row_path=path)


async def test_errors_are_recorded_as_zero_and_invalidate_comparison(tmp_path):
    cases = [RetrievalCase(id="query", intent="generation", query="标题", expected_card_ids=["a"])]
    summary, rows = await compare_retrieval(
        [make_card("a")], cases, FakeVectorStore(error=RuntimeError("service down"))
    )
    assert summary["queries"] == 1 and summary["errors"] == 1
    assert not summary["valid_comparison"]
    assert summary["conditions"]["hybrid"]["macro_recall"] == 0
    assert rows[0]["error"] == "RuntimeError: service down"


async def test_invalid_labels_cannot_silently_shrink_denominator():
    cases = [
        RetrievalCase(id="bad-label", intent="generation", query="标题", expected_card_ids=["a"])
    ]
    with pytest.raises(ValueError, match="excluded by production filters"):
        await compare_retrieval([make_card("a", status="candidate")], cases, FakeVectorStore())
