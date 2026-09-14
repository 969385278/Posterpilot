from pathlib import Path

from app.rag.models import KnowledgeCard, RetrievalCase, SourceChunk


class KnowledgeRepository:
    def __init__(self, knowledge_dir: Path | str):
        self.knowledge_dir = Path(knowledge_dir)

    def list_cards(self) -> list[KnowledgeCard]:
        return self._load_jsonl("knowledge_cards.jsonl", KnowledgeCard)

    def list_chunks(self) -> list[SourceChunk]:
        return self._load_jsonl("source_chunks.jsonl", SourceChunk)

    def list_retrieval_cases(self) -> list[RetrievalCase]:
        path = self.knowledge_dir / "retrieval_cases.json"
        return [RetrievalCase.model_validate(item) for item in _read_json(path)]

    def approved_cards(self) -> list[KnowledgeCard]:
        return [card for card in self.list_cards() if card.review_status == "approved"]

    def _load_jsonl(self, name: str, model_type: type):
        path = self.knowledge_dir / name
        return [
            model_type.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]


def _read_json(path: Path):
    import json

    return json.loads(path.read_text(encoding="utf-8"))

