import argparse
import json
from pathlib import Path

import yaml
from pypdf import PdfReader

from app.rag.ingestion.chunker import clean_page_text
from app.rag.models import SourceManifest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data/knowledge/source_manifest.yaml"
DEFAULT_OUTPUT = ROOT / "data/knowledge/pdf_inventory.json"


def inventory_pdf(path: Path, source_id: str) -> dict[str, object]:
    reader = PdfReader(str(path))
    text_lengths: list[int] = []
    for page in reader.pages:
        text = clean_page_text(page.extract_text() or "")
        text_lengths.append(len(text))
    text_pages = [index + 1 for index, length in enumerate(text_lengths) if length >= 40]
    return {
        "source_id": source_id,
        "path": path.relative_to(ROOT).as_posix(),
        "total_pages": len(reader.pages),
        "pages_with_text": len(text_pages),
        "pages_without_text": len(reader.pages) - len(text_pages),
        "text_characters": sum(text_lengths),
        "text_page_numbers": text_pages,
    }


def build_inventory() -> list[dict[str, object]]:
    manifest = SourceManifest.model_validate(
        yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    )
    return [
        inventory_pdf(ROOT / source.path, source.id)
        for source in manifest.sources
        if source.source_type == "pdf" and source.path
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect PDF text-layer availability.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    inventory = build_inventory()
    if not args.no_write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    for item in inventory:
        print(
            f"{item['source_id']}: {item['total_pages']} pages, "
            f"{item['pages_with_text']} with text, "
            f"{item['pages_without_text']} without text, "
            f"{item['text_characters']} characters."
        )


if __name__ == "__main__":
    main()

