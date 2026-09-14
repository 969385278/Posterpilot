from collections.abc import Sequence

from app.rag.models import KnowledgeCitation, RetrievalMatch


def build_citations(matches: Sequence[RetrievalMatch]) -> list[KnowledgeCitation]:
    return [
        KnowledgeCitation(
            card_id=match.card.id,
            title=match.card.title,
            source_id=match.card.source_id,
            source_pages=match.card.source_pages,
            source_locator=match.card.source_locator,
            source_url=match.card.source_url,
            similarity=match.similarity,
        )
        for match in matches
    ]
