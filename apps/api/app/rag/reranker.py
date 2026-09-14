import re

from app.rag.models import KnowledgeCard


def lexical_similarity(card: KnowledgeCard, query: str) -> float:
    card_text = " ".join(
        [
            card.title,
            card.content,
            *card.retrieval_aliases,
            *card.signals,
            *card.tags,
        ]
    )
    return bigram_dice(card_text, query)


def hybrid_similarity(vector_similarity: float, lexical_score: float) -> float:
    return min(1.0, max(0.0, vector_similarity * 0.85 + lexical_score * 0.15))


def bigram_dice(left: str, right: str) -> float:
    left_bigrams = _bigrams(_normalize(left))
    right_bigrams = _bigrams(_normalize(right))
    if not left_bigrams or not right_bigrams:
        return 0.0
    overlap = len(left_bigrams.intersection(right_bigrams))
    return 2 * overlap / (len(left_bigrams) + len(right_bigrams))


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", value.lower())


def _bigrams(value: str) -> set[str]:
    return {value[index : index + 2] for index in range(max(0, len(value) - 1))}

