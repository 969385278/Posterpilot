import hashlib
import json
from pathlib import Path
from time import perf_counter

from app.rag.models import RetrievalRequest, VectorHit
from app.rag.reranker import lexical_similarity
from app.rag.retriever import KnowledgeRetriever


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def retrieval_metrics(expected, ranked, excluded=()):
    relevant = set(expected)
    if not relevant:
        raise ValueError("Recall requires at least one labelled relevant document")
    ids = list(dict.fromkeys(ranked))
    found = relevant.intersection(ids)
    ranks = [i + 1 for i, card_id in enumerate(ids) if card_id in relevant]
    return {
        "recall": len(found) / len(relevant),
        "hit_rate": float(bool(found)),
        "reciprocal_rank": 1 / min(ranks) if ranks else 0.0,
        "forbidden_hits": sorted(set(excluded).intersection(ids)),
        "missing_relevant": sorted(relevant.difference(ids)),
    }


class FrozenRepository:
    def __init__(self, cards):
        self.cards = cards

    def list_cards(self):
        return self.cards


class CapturedStore:
    """Replay actual captured vector hits into the production hybrid retriever."""

    def __init__(self, hits):
        self.hits = hits

    async def search(self, query, *, candidate_ids, limit):
        return [hit for hit in self.hits if hit.id in candidate_ids][:limit]


async def compare_retrieval(cards, cases, vector_store, *, top_k=5, row_path: Path | None = None):
    if not 1 <= top_k <= 20:
        raise ValueError("top_k must be 1 to 20")
    if not cards or not cases:
        raise ValueError("Empty corpus or evaluation dataset")
    if len({card.id for card in cards}) != len(cards) or len({case.id for case in cases}) != len(
        cases
    ):
        raise ValueError("Duplicate corpus or case IDs")
    repository = FrozenRepository(cards)
    by_id = {card.id: card for card in cards}
    filterer = KnowledgeRetriever(repository, CapturedStore([]))
    requests = []
    for case in cases:
        request = RetrievalRequest(
            intent=case.intent,
            query=case.query,
            target_roles=case.context.get("targetAois", []),
            top_k=top_k,
            min_similarity=0.0,
        )
        candidates = filterer._filter_candidates(request)
        ids = {card.id for card in candidates}
        if not set(case.expected_card_ids).issubset(ids):
            raise ValueError(f"{case.id}: relevant labels excluded by production filters")
        if set(case.expected_card_ids).intersection(case.excluded_card_ids):
            raise ValueError(f"{case.id}: contradictory labels")
        if not set(case.excluded_card_ids).issubset(by_id):
            raise ValueError(f"{case.id}: unknown excluded label")
        requests.append((case, request, [card.id for card in candidates]))
    rows = []
    stream = row_path.open("x", encoding="utf-8") if row_path else None
    try:
        for case, request, ids in requests:
            start = perf_counter()
            row = {
                "id": case.id,
                "query": case.query,
                "request": request.model_dump(mode="json"),
                "expected_card_ids": case.expected_card_ids,
                "excluded_card_ids": case.excluded_card_ids,
                "candidate_ids": ids,
                "conditions": {},
                "error": None,
            }
            try:
                hits = await vector_store.search(case.query, candidate_ids=ids, limit=top_k * 3)
                hits = [VectorHit.model_validate(hit) for hit in hits]
                if len({hit.id for hit in hits}) != len(hits) or any(
                    hit.id not in ids for hit in hits
                ):
                    raise ValueError("Vector store returned duplicate or ineligible IDs")
                hits.sort(key=lambda hit: hit.similarity, reverse=True)
                row["captured_hits"] = [
                    {
                        **hit.model_dump(),
                        "lexical_similarity": lexical_similarity(by_id[hit.id], case.query),
                    }
                    for hit in hits
                ]
                hybrid = await KnowledgeRetriever(repository, CapturedStore(hits)).retrieve(request)
                predictions = {
                    "vector_only": [hit.id for hit in hits[:top_k]],
                    "hybrid": [match.card.id for match in hybrid.matches],
                }
                row["hybrid_matches"] = [match.model_dump(mode="json") for match in hybrid.matches]
            except Exception as error:
                row["error"] = f"{type(error).__name__}: {error}"
                predictions = {"vector_only": [], "hybrid": []}
            for condition, prediction in predictions.items():
                row["conditions"][condition] = {
                    "ranked_ids": prediction,
                    **retrieval_metrics(case.expected_card_ids, prediction, case.excluded_card_ids),
                }
            row["shared_retrieval_seconds"] = perf_counter() - start
            rows.append(row)
            if stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
    finally:
        if stream:
            stream.close()
    summary = {
        "queries": len(rows),
        "top_k": top_k,
        "errors": sum(row["error"] is not None for row in rows),
        "conditions": {},
    }
    for condition in ("vector_only", "hybrid"):
        results = [row["conditions"][condition] for row in rows]
        summary["conditions"][condition] = {
            "macro_recall": sum(item["recall"] for item in results) / len(results),
            "hit_rate": sum(item["hit_rate"] for item in results) / len(results),
            "mrr": sum(item["reciprocal_rank"] for item in results) / len(results),
            "queries_with_forbidden_hits": sum(bool(item["forbidden_hits"]) for item in results),
        }
    summary["hybrid_minus_vector"] = {
        key: summary["conditions"]["hybrid"][key] - summary["conditions"]["vector_only"][key]
        for key in ("macro_recall", "hit_rate", "mrr")
    }
    summary["valid_comparison"] = summary["errors"] == 0
    return summary, rows
