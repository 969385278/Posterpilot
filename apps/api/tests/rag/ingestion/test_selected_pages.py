from pathlib import Path

import pytest

from app.rag.ingestion.selected_ocr import extract_selected_pages, validate_selected_pages


class FakeOcrEngine:
    def extract(self, _pdf_path: Path, page_number: int) -> str:
        return f"第 {page_number} 页的 OCR 文本"


@pytest.mark.parametrize("pages", [[], [0], [4], [2, 2]])
def test_selected_pages_reject_invalid_selection(pages: list[int]) -> None:
    with pytest.raises(ValueError):
        validate_selected_pages(pages, total_pages=3)


def test_selected_ocr_only_calls_explicit_pages(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"fake fixture; engine is injected")

    pages = extract_selected_pages(
        pdf_path,
        selected_pages=[2, 5],
        total_pages=8,
        engine=FakeOcrEngine(),
    )

    assert [page.page_number for page in pages] == [2, 5]
    assert pages[0].text == "第 2 页的 OCR 文本"

