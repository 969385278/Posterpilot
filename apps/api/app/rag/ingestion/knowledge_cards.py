from typing import Any

from app.rag.models import KnowledgeCard, SourceChunk


def build_candidate_card(payload: dict[str, Any], source_chunk: SourceChunk) -> KnowledgeCard:
    """Attach immutable source data to a model-produced candidate card."""
    candidate = {
        **payload,
        "source_id": source_chunk.source_id,
        "source_pages": list(range(source_chunk.page_start, source_chunk.page_end + 1)),
        "source_locator": source_chunk.id,
        "review_status": "candidate",
    }
    return KnowledgeCard.model_validate(candidate)

