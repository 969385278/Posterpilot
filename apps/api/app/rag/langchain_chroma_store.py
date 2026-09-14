from collections.abc import Sequence
from typing import Any
from urllib.parse import urlparse

import chromadb
from langchain_chroma import Chroma

from app.rag.models import VectorHit


class ChromaVectorStore:
    def __init__(self, store: Any):
        self.store = store

    async def search(
        self,
        query: str,
        *,
        candidate_ids: Sequence[str],
        limit: int,
    ) -> list[VectorHit]:
        allowed_ids = set(candidate_ids)
        if not allowed_ids:
            return []
        results = await self.store.asimilarity_search_with_relevance_scores(
            query,
            k=limit,
            filter={"card_id": {"$in": list(candidate_ids)}},
        )
        hits: list[VectorHit] = []
        for document, similarity in results:
            card_id = str(document.metadata.get("card_id", ""))
            if card_id not in allowed_ids:
                continue
            hits.append(
                VectorHit(
                    id=card_id,
                    similarity=min(1.0, max(0.0, float(similarity))),
                )
            )
        return hits


def create_remote_chroma(
    *,
    chroma_url: str,
    collection_name: str,
    embedding_function: Any,
) -> Chroma:
    parsed = urlparse(chroma_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("CHROMA_URL must be an http or https URL")
    client = chromadb.HttpClient(
        host=parsed.hostname,
        port=parsed.port or (443 if parsed.scheme == "https" else 80),
        ssl=parsed.scheme == "https",
    )
    return Chroma(
        client=client,
        collection_name=collection_name,
        embedding_function=embedding_function,
    )

