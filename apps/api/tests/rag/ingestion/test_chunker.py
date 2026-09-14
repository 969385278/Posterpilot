from app.rag.ingestion.chunker import clean_page_text, split_page_text


def test_clean_page_text_removes_standalone_page_numbers_and_repeated_space() -> None:
    raw = "第 2 章  海报设计\n\n  12  \n视觉层级   决定信息阅读顺序。\n"

    cleaned = clean_page_text(raw)

    assert cleaned == "第 2 章 海报设计\n视觉层级决定信息阅读顺序。"


def test_clean_page_text_repairs_cjk_line_wrap_spaces() -> None:
    raw = "AIGC 技术正引领设计行业迈\n向全新方向，并深度解 析设计流程。"

    assert clean_page_text(raw) == "AIGC 技术正引领设计行业迈向全新方向，并深度解析设计流程。"


def test_split_page_text_prefers_paragraph_boundaries() -> None:
    text = "第一段介绍视觉层级。" * 12 + "\n\n" + "第二段讨论海报留白。" * 12

    chunks = split_page_text(text, target_chars=120, overlap_chars=20)

    assert len(chunks) >= 2
    assert all(chunk.strip() for chunk in chunks)
    assert all(len(chunk) <= 160 for chunk in chunks)
    assert "第一段介绍视觉层级" in chunks[0]
    assert "第二段讨论海报留白" in chunks[-1]


def test_split_page_text_does_not_emit_short_orphan_chunk() -> None:
    text = "海报构图需要建立明确的信息层级。" * 15 + "结论。"

    chunks = split_page_text(text, target_chars=140, overlap_chars=20, min_chars=40)

    assert len(chunks[-1]) >= 40
    assert "结论。" in chunks[-1]
