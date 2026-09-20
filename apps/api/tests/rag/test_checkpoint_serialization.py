from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic import HttpUrl

from app.rag.models import KnowledgeCard, RetrievalMatch, RetrievalResult


def test_sourced_retrieval_survives_checkpoint_roundtrip():
    card = KnowledgeCard(
        id="web-rule",
        knowledge_type="rule",
        category="contrast",
        title="文字对比",
        content="检查文字与背景的局部对比。",
        actions=["检查局部背景"],
        source_id="w3c",
        source_locator="G18",
        source_url="https://www.w3.org/WAI/WCAG22/Techniques/general/G18",
        review_status="approved",
    )
    original = RetrievalResult(
        query="文字看不清",
        matches=[
            RetrievalMatch(
                card=card,
                similarity=0.8,
                vector_similarity=0.7,
                lexical_similarity=0.9,
            )
        ],
    )
    serializer = JsonPlusSerializer(allowed_msgpack_modules=[RetrievalResult])
    encoded = serializer.dumps_typed(original)
    restored = serializer.loads_typed(encoded)
    assert encoded[0] == "msgpack"
    assert restored == original
    assert isinstance(restored.matches[0].card.source_url, HttpUrl)
    assert restored.matches[0].card.source_locator == "G18"


def test_card_without_url_remains_checkpoint_compatible():
    card = KnowledgeCard(
        id="internal-rule",
        knowledge_type="rule",
        category="layout",
        title="规则",
        content="内部草案",
        actions=["检查布局"],
    )
    serializer = JsonPlusSerializer(allowed_msgpack_modules=[KnowledgeCard])
    assert serializer.loads_typed(serializer.dumps_typed(card)) == card
