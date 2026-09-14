from pathlib import Path
from typing import Protocol

from app.rag.ingestion.chunker import clean_page_text
from app.rag.ingestion.pdf_text import ExtractedPage


class OcrEngine(Protocol):
    def extract(self, pdf_path: Path, page_number: int) -> str: ...


def validate_selected_pages(selected_pages: list[int], total_pages: int) -> list[int]:
    if not selected_pages:
        raise ValueError("selected OCR requires at least one explicit page")
    if len(selected_pages) != len(set(selected_pages)):
        raise ValueError("selected OCR pages must be unique")
    if any(page < 1 or page > total_pages for page in selected_pages):
        raise ValueError(f"selected OCR pages must be between 1 and {total_pages}")
    return sorted(selected_pages)


def extract_selected_pages(
    pdf_path: Path | str,
    *,
    selected_pages: list[int],
    total_pages: int,
    engine: OcrEngine,
) -> list[ExtractedPage]:
    path = Path(pdf_path)
    pages = validate_selected_pages(selected_pages, total_pages)
    return [
        ExtractedPage(
            page_number=page_number,
            text=clean_page_text(engine.extract(path, page_number)),
            extraction_method="ocr",
        )
        for page_number in pages
    ]
