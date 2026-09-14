from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from app.rag.ingestion.chunker import clean_page_text


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    page_number: int
    text: str
    extraction_method: str


def extract_pdf_pages(
    pdf_path: Path | str,
    *,
    selected_pages: list[int] | None = None,
) -> list[ExtractedPage]:
    path = Path(pdf_path)
    reader = PdfReader(str(path))
    total_pages = len(reader.pages)
    page_numbers = selected_pages or list(range(1, total_pages + 1))
    _validate_page_numbers(page_numbers, total_pages)

    extracted: list[ExtractedPage] = []
    for page_number in page_numbers:
        raw_text = reader.pages[page_number - 1].extract_text() or ""
        extracted.append(
            ExtractedPage(
                page_number=page_number,
                text=clean_page_text(raw_text),
                extraction_method="text",
            )
        )
    return extracted


def _validate_page_numbers(page_numbers: list[int], total_pages: int) -> None:
    if not page_numbers:
        raise ValueError("at least one page must be selected")
    if len(page_numbers) != len(set(page_numbers)):
        raise ValueError("selected pages must be unique")
    if any(page < 1 or page > total_pages for page in page_numbers):
        raise ValueError(f"selected pages must be between 1 and {total_pages}")

