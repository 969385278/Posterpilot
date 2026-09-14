import argparse
from pathlib import Path

import yaml

from app.rag.ingestion.chunker import split_page_text
from app.rag.ingestion.pdf_text import extract_pdf_pages
from app.rag.models import SourceChunk, SourceDocument, SourceManifest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data/knowledge/source_manifest.yaml"
CHUNKS_PATH = ROOT / "data/knowledge/source_chunks.jsonl"


def load_manifest() -> SourceManifest:
    return SourceManifest.model_validate(
        yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    )


def chunks_for_pdf_text(source: SourceDocument) -> list[SourceChunk]:
    if not source.path:
        raise ValueError(f"Source {source.id} has no PDF path")
    pages = extract_pdf_pages(ROOT / source.path, selected_pages=source.selected_pages or None)
    chunks: list[SourceChunk] = []
    for page in pages:
        if len(page.text) < 80:
            continue
        title = page.text.splitlines()[0][:120]
        for chunk_index, content in enumerate(split_page_text(page.text), 1):
            chunks.append(
                SourceChunk(
                    id=f"{source.id}-p{page.page_number:03d}-c{chunk_index:02d}",
                    source_id=source.id,
                    source_path=source.path,
                    page_start=page.page_number,
                    page_end=page.page_number,
                    title=title,
                    content=content,
                    extraction_method="text",
                    quality_status="pending_review",
                )
            )
    return chunks


def load_existing_chunks() -> list[SourceChunk]:
    if not CHUNKS_PATH.exists():
        return []
    return [
        SourceChunk.model_validate_json(line)
        for line in CHUNKS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_chunks(chunks: list[SourceChunk]) -> None:
    lines = [chunk.model_dump_json() for chunk in chunks]
    CHUNKS_PATH.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare traceable PDF source chunks.")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest()
    source = next((item for item in manifest.sources if item.id == args.source_id), None)
    if source is None:
        raise ValueError(f"Unknown source: {args.source_id}")
    if source.extraction_mode != "pdf_text":
        raise ValueError(
            f"Source {source.id} uses {source.extraction_mode}; "
            "selected OCR requires reviewed page numbers and an OCR engine."
        )

    new_chunks = chunks_for_pdf_text(source)
    if args.dry_run:
        print(f"Dry run: {source.id} would produce {len(new_chunks)} pending-review chunks.")
        return

    retained = [chunk for chunk in load_existing_chunks() if chunk.source_id != source.id]
    write_chunks([*retained, *new_chunks])
    print(f"Wrote {len(new_chunks)} pending-review chunks for {source.id}.")


if __name__ == "__main__":
    main()

