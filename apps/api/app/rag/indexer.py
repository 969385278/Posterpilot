from collections.abc import Sequence
from typing import Protocol

from langchain_core.documents import Document

from app.rag.models import KnowledgeCard


class IndexStore(Protocol):
    def reset_collection(self) -> None: ...

    def add_documents(self, documents: Sequence[Document], *, ids: Sequence[str]) -> None: ...


class KnowledgeIndexer:
    def __init__(self, store: IndexStore):
        self.store = store

    def rebuild(self, cards: Sequence[KnowledgeCard]) -> int:
        approved = [card for card in cards if card.review_status == "approved"]
        documents = [card_to_document(card) for card in approved]
        ids = [card.id for card in approved]
        self.store.reset_collection()
        if documents:
            self.store.add_documents(documents, ids=ids)
        return len(documents)


def card_to_document(card: KnowledgeCard) -> Document:
    sections = [
        card.title,
        card.content,
        f"检索别名：{'；'.join(card.retrieval_aliases)}" if card.retrieval_aliases else "",
        f"问题信号：{'；'.join(card.signals)}" if card.signals else "",
        f"可执行动作：{'；'.join(card.actions)}",
        f"约束：{'；'.join(card.constraints)}" if card.constraints else "",
    ]
    return Document(
        page_content="\n".join(section for section in sections if section),
        metadata={
            "card_id": card.id,
            "category": card.category,
            "knowledge_type": card.knowledge_type,
            "review_status": card.review_status,
            "intents": ",".join(card.intents),
            "target_roles": ",".join(card.target_roles),
            "source_id": card.source_id,
        },
    )

