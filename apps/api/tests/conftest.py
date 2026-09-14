from collections.abc import Iterator

import pytest

from app.rag.models import KnowledgeCard


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("POSTERPILOT_ENV", "test")
    yield


@pytest.fixture
def approved_card() -> KnowledgeCard:
    return KnowledgeCard.model_validate(
        {
            "id": "title-focus-001",
            "knowledge_type": "rule",
            "category": "visual_hierarchy",
            "title": "主标题应成为第一视觉焦点",
            "content": "标题的信息层级应高于正文。",
            "signals": ["标题与正文大小接近"],
            "actions": ["增大标题字号"],
            "constraints": ["不得删除活动信息"],
            "retrieval_aliases": ["标题不醒目"],
            "intents": ["generation", "optimization"],
            "target_roles": ["title"],
            "source_id": "nng-visual-design",
            "source_locator": "Visual hierarchy definition",
            "review_status": "approved",
            "confidence": 0.9,
        }
    )
