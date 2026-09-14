import argparse
import asyncio
from collections.abc import Sequence

from app.core.config import get_settings
from app.providers.embedding.ollama import create_ollama_embeddings
from app.rag.langchain_chroma_store import ChromaVectorStore, create_remote_chroma
from app.rag.models import KnowledgeCard, RetrievalRequest, VectorHit
from app.rag.repository import KnowledgeRepository
from app.rag.reranker import lexical_similarity
from app.rag.retriever import KnowledgeRetriever


class OfflineLexicalStore:
    def __init__(self, cards: Sequence[KnowledgeCard]):
        self.cards = {card.id: card for card in cards}

    async def search(
        self,
        query: str,
        *,
        candidate_ids: Sequence[str],
        limit: int,
    ) -> list[VectorHit]:
        hits = [
            VectorHit(id=card_id, similarity=lexical_similarity(self.cards[card_id], query))
            for card_id in candidate_ids
            if card_id in self.cards
        ]
        return sorted(hits, key=lambda hit: hit.similarity, reverse=True)[:limit]


async def evaluate(*, offline: bool) -> int:
    settings = get_settings()
    repository = KnowledgeRepository(settings.data_dir / "knowledge")
    cards = repository.list_cards()
    if offline:
        vector_store = OfflineLexicalStore(cards)
    else:
        embeddings = create_ollama_embeddings(
            model=settings.ollama_embedding_model,
            base_url=settings.ollama_base_url,
            timeout_seconds=settings.embedding_timeout_seconds,
        )
        chroma = create_remote_chroma(
            chroma_url=settings.chroma_url,
            collection_name=settings.rag_collection_name,
            embedding_function=embeddings,
        )
        vector_store = ChromaVectorStore(chroma)

    retriever = KnowledgeRetriever(repository, vector_store)
    cases = repository.list_retrieval_cases()
    recalled = 0
    reciprocal_rank_total = 0.0
    failures: list[str] = []
    for case in cases:
        target_roles = case.context.get("targetAois", [])
        result = await retriever.retrieve(
            RetrievalRequest(
                intent=case.intent,
                query=case.query,
                target_roles=target_roles,
                top_k=3,
                min_similarity=0.0,
            )
        )
        result_ids = [match.card.id for match in result.matches]
        expected = set(case.expected_card_ids)
        matching_ranks = [index + 1 for index, card_id in enumerate(result_ids) if card_id in expected]
        if matching_ranks:
            recalled += 1
            reciprocal_rank_total += 1 / min(matching_ranks)
        else:
            failures.append(f"{case.id}: expected {sorted(expected)}, got {result_ids}")

    total = len(cases)
    recall_at_3 = recalled / total if total else 0.0
    mrr = reciprocal_rank_total / total if total else 0.0
    mode = "offline lexical baseline" if offline else "Ollama + Chroma"
    print(f"Retrieval evaluation ({mode}): Recall@3={recall_at_3:.3f}, MRR={mrr:.3f}")
    for failure in failures:
        print(f"FAIL {failure}")
    return 0 if not failures else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate fixed PosterPilot retrieval cases.")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(evaluate(offline=args.offline)))


if __name__ == "__main__":
    main()

