import json
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

from app.rag.models import KnowledgeCard, RetrievalCase, SourceChunk, SourceManifest

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "data/knowledge"
ModelT = TypeVar("ModelT", bound=BaseModel)


def load_jsonl(path: Path, model_type: type[ModelT]) -> list[ModelT]:
    if not path.exists():
        raise ValueError(f"Missing knowledge file: {path.relative_to(ROOT)}")
    models: list[ModelT] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            models.append(model_type.model_validate_json(raw_line))
        except Exception as error:
            raise ValueError(f"Invalid {path.name} line {line_number}: {error}") from error
    return models


def require_unique(values: list[str], label: str) -> None:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise ValueError(f"Duplicate {label}: {', '.join(duplicates)}")


def validate() -> dict[str, int]:
    manifest_data = yaml.safe_load(
        (KNOWLEDGE_DIR / "source_manifest.yaml").read_text(encoding="utf-8")
    )
    manifest = SourceManifest.model_validate(manifest_data)
    cards = load_jsonl(KNOWLEDGE_DIR / "knowledge_cards.jsonl", KnowledgeCard)
    chunks = load_jsonl(KNOWLEDGE_DIR / "source_chunks.jsonl", SourceChunk)
    cases_data = json.loads(
        (KNOWLEDGE_DIR / "retrieval_cases.json").read_text(encoding="utf-8")
    )
    cases = [RetrievalCase.model_validate(case) for case in cases_data]

    source_ids = {source.id for source in manifest.sources}
    card_ids = {card.id for card in cards}
    require_unique([card.id for card in cards], "knowledge card ids")
    require_unique([chunk.id for chunk in chunks], "source chunk ids")
    require_unique([case.id for case in cases], "retrieval case ids")

    missing_sources = sorted({card.source_id for card in cards if card.source_id not in source_ids})
    if missing_sources:
        raise ValueError(f"Knowledge cards reference unknown sources: {', '.join(missing_sources)}")

    missing_chunk_sources = sorted(
        {chunk.source_id for chunk in chunks if chunk.source_id not in source_ids}
    )
    if missing_chunk_sources:
        raise ValueError(
            f"Source chunks reference unknown sources: {', '.join(missing_chunk_sources)}"
        )

    for source in manifest.sources:
        if source.source_type == "pdf" and source.path and not (ROOT / source.path).exists():
            raise ValueError(f"PDF source does not exist: {source.path}")

    missing_expected = sorted(
        {
            expected_id
            for case in cases
            for expected_id in case.expected_card_ids
            if expected_id not in card_ids
        }
    )
    if missing_expected:
        raise ValueError(f"Retrieval cases reference unknown cards: {', '.join(missing_expected)}")

    approved_cards = [card for card in cards if card.review_status == "approved"]
    return {
        "sources": len(manifest.sources),
        "chunks": len(chunks),
        "cards": len(cards),
        "approved_cards": len(approved_cards),
        "retrieval_cases": len(cases),
    }


def main() -> None:
    summary = validate()
    print(
        "Knowledge validation passed: "
        f"{summary['sources']} sources, {summary['chunks']} chunks, "
        f"{summary['cards']} cards ({summary['approved_cards']} approved), "
        f"{summary['retrieval_cases']} retrieval cases."
    )


if __name__ == "__main__":
    main()
