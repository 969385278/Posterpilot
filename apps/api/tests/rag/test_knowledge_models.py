import pytest
from pydantic import ValidationError

from app.rag.models import KnowledgeCard, SourceDocument, SourceManifest


def test_approved_card_requires_traceable_source() -> None:
    with pytest.raises(ValidationError, match="traceable source"):
        KnowledgeCard.model_validate(
            {
                "id": "layout-title-focus-001",
                "knowledge_type": "rule",
                "category": "visual_hierarchy",
                "title": "主标题应形成明确的第一层级",
                "content": "标题层级应与用户定义的信息优先级一致。",
                "signals": ["标题与正文大小接近"],
                "actions": ["增大标题与正文的字号差"],
                "constraints": ["不得删除用户要求的信息"],
                "source_id": "",
                "source_pages": [],
                "review_status": "approved",
            }
        )


def test_approved_card_accepts_pdf_page_citation() -> None:
    card = KnowledgeCard.model_validate(
        {
            "id": "layout-title-focus-001",
            "knowledge_type": "rule",
            "category": "visual_hierarchy",
            "title": "主标题应形成明确的第一层级",
            "content": "标题层级应与用户定义的信息优先级一致。",
            "signals": ["标题与正文大小接近"],
            "actions": ["增大标题与正文的字号差"],
            "constraints": ["不得删除用户要求的信息"],
            "source_id": "lai-poster-design",
            "source_pages": [42, 43],
            "review_status": "approved",
        }
    )

    assert card.source_pages == [42, 43]


def test_selected_ocr_source_requires_selected_pages() -> None:
    with pytest.raises(ValidationError, match="selected pages"):
        SourceDocument.model_validate(
            {
                "id": "lai-poster-design",
                "title": "海报设计资料",
                "source_type": "pdf",
                "path": "docs/pdf/lai.pdf",
                "extraction_mode": "selected_ocr",
                "total_pages": 291,
                "selected_pages": [],
                "status": "selected",
            }
        )


def test_manifest_rejects_duplicate_source_ids() -> None:
    source = {
        "id": "qinghua-aigc-poster",
        "title": "AIGC 海报设计",
        "source_type": "pdf",
        "path": "docs/pdf/qinghua.pdf",
        "extraction_mode": "pdf_text",
        "total_pages": 44,
        "selected_pages": [],
        "status": "pending_review",
    }

    with pytest.raises(ValidationError, match="unique"):
        SourceManifest.model_validate({"version": 1, "sources": [source, source]})

