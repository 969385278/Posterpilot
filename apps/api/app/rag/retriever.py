from collections.abc import Sequence
from typing import Protocol

from app.rag.models import (
    KnowledgeCard,
    RetrievalMatch,
    RetrievalRequest,
    RetrievalResult,
    VectorHit,
)
from app.rag.reranker import hybrid_similarity, lexical_similarity

_ROLE_ALIASES = {
    "event_info": {"event_info", "time_venue"},
    "time_venue": {"event_info", "time_venue"},
    "main_visual": {"main_visual", "visual"},
    "visual": {"main_visual", "visual"},
}


class CardRepository(Protocol):
    def list_cards(self) -> list[KnowledgeCard]: ...


class VectorStore(Protocol):
    async def search(
        self,
        query: str,
        *,
        candidate_ids: Sequence[str],
        limit: int,
    ) -> list[VectorHit]: ...


class KnowledgeRetriever:
    def __init__(self, repository: CardRepository, vector_store: VectorStore):
        self.repository = repository
        self.vector_store = vector_store

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        candidates = self._filter_candidates(request)
        candidate_ids = [card.id for card in candidates]
        if not candidates:
            return RetrievalResult(
                query=request.query,
                candidate_ids=[],
                fallback_reason="no_metadata_candidates",
            )

        try:
            hits = await self.vector_store.search(
                request.query,
                candidate_ids=candidate_ids,
                limit=max(request.top_k * 3, request.top_k),
            )
        except Exception as error:
            return RetrievalResult(
                query=request.query,
                candidate_ids=candidate_ids,
                fallback_reason="vector_store_unavailable",
                error=str(error),
            )

        cards_by_id = {card.id: card for card in candidates}
        matches: list[RetrievalMatch] = []
        for hit in hits:
            card = cards_by_id.get(hit.id)
            if card is None:
                continue
            lexical_score = lexical_similarity(card, request.query)
            combined = hybrid_similarity(hit.similarity, lexical_score)
            if combined < request.min_similarity:
                continue
            matches.append(
                RetrievalMatch(
                    card=card,
                    similarity=combined,
                    vector_similarity=hit.similarity,
                    lexical_similarity=lexical_score,
                )
            )

        matches.sort(key=lambda match: (match.similarity, match.card.confidence), reverse=True)
        selected = matches[: request.top_k]
        return RetrievalResult(
            query=request.query,
            matches=selected,
            candidate_ids=candidate_ids,
            fallback_reason=None if selected else "below_similarity_threshold",
        )

    def _filter_candidates(self, request: RetrievalRequest) -> list[KnowledgeCard]:
        requested_roles = _expand_roles(request.target_roles)
        return [
            card
            for card in self.repository.list_cards()
            if (
                card.review_status == "approved"
                or (request.include_candidates and card.review_status == "candidate")
            )
            and (not card.intents or request.intent in card.intents)
            and (
                not requested_roles
                or not card.target_roles
                or "any" in card.target_roles
                or bool(requested_roles.intersection(_expand_roles(card.target_roles)))
            )
        ]


def _expand_roles(roles: Sequence[str]) -> set[str]:
    expanded: set[str] = set()
    for role in roles:
        expanded.update(_ROLE_ALIASES.get(role, {role}))
    return expanded
