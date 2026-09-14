from app.rag.citations import build_citations
from app.rag.models import KnowledgeCard, RetrievalMatch


def test_citation_preserves_source_locator_and_score() -> None:
    card = KnowledgeCard.model_validate(
        {
            "id": "layout-title-focus-001",
            "knowledge_type": "rule",
            "category": "visual_hierarchy",
            "title": "主标题应成为第一视觉焦点",
            "content": "标题的信息层级应高于正文。",
            "actions": ["增大标题字号"],
            "source_id": "lai-poster-design",
            "source_pages": [42, 43],
            "source_locator": "视觉层级",
            "review_status": "approved",
        }
    )
    match = RetrievalMatch(
        card=card,
        similarity=0.91,
        vector_similarity=0.9,
        lexical_similarity=0.95,
    )

    citations = build_citations([match])

    assert citations[0].card_id == card.id
    assert citations[0].source_pages == [42, 43]
    assert citations[0].source_locator == "视觉层级"
    assert citations[0].similarity == 0.91

