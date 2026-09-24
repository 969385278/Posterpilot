"""Paired retrieval experiment using frozen data and actual Ollama + isolated Chroma."""

import argparse
import asyncio
import importlib.metadata
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.core.paths import PROJECT_ROOT
from app.experiments.retrieval import compare_retrieval, digest
from app.providers.embedding.asset_ollama import AssetOllamaEmbeddings
from app.rag.indexer import card_to_document
from app.rag.langchain_chroma_store import ChromaVectorStore
from app.rag.models import RetrievalCase
from app.rag.repository import KnowledgeRepository
from langchain_chroma import Chroma


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


async def run(args):
    root = args.output_root / f"retrieval-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    cards = KnowledgeRepository(args.knowledge_dir).list_cards()
    cases = [
        RetrievalCase.model_validate(value)
        for value in json.loads(args.cases.read_text(encoding="utf-8"))
    ]
    frozen_cards = [card.model_dump(mode="json") for card in cards]
    frozen_cases = [case.model_dump(mode="json") for case in cases]
    save(root / "corpus.json", frozen_cards)
    save(root / "cases.json", frozen_cases)
    source_paths = [
        PROJECT_ROOT / "apps/api/app/rag/retriever.py",
        PROJECT_ROOT / "apps/api/app/rag/reranker.py",
        PROJECT_ROOT / "apps/api/app/rag/indexer.py",
        PROJECT_ROOT / "apps/api/app/rag/langchain_chroma_store.py",
        PROJECT_ROOT / "apps/api/app/experiments/retrieval.py",
        Path(__file__).resolve(),
    ]
    for path in source_paths:
        target = root / "source" / path.relative_to(PROJECT_ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "state": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "dataset_kind": "development_regression_not_independent_holdout",
        "corpus_hash": digest(frozen_cards),
        "cases_hash": digest(frozen_cases),
        "top_k": args.top_k,
        "min_similarity": 0.0,
        "comparison": "Same metadata candidates and captured vector hits; production hybrid reranking vs pure vector ranking",
        "embedding_model": args.model,
        "chroma_mode": "isolated_persistent_local_default_distance",
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("chromadb", "langchain-chroma", "langchain-ollama")
        },
        "python": sys.version,
        "code_hashes": {
            path.relative_to(PROJECT_ROOT).as_posix(): digest(
                path.read_text(encoding="utf-8")
            )
            for path in source_paths
        },
        "limitations": [
            "Development queries may overlap retrieval aliases; not independent labels.",
            "No automatic thresholds/weights tuning on this dataset.",
            "Errors remain in denominators and invalidate the comparison.",
            "No claims about answer quality, online traffic, or resume percentages.",
        ],
    }
    save(root / "manifest.json", manifest)
    print(f"Experiment directory: {root}", flush=True)
    try:
        embeddings = AssetOllamaEmbeddings(
            model=args.model, base_url=args.base_url, timeout_seconds=120
        )
        identity = embeddings.identity()
        manifest["embedding_identity"] = identity
        save(root / "manifest.json", manifest)
        store = Chroma(
            collection_name="paired_retrieval",
            persist_directory=str(root / "chroma"),
            embedding_function=embeddings.provider,
        )
        approved = [card for card in cards if card.review_status == "approved"]
        store.add_documents(
            [card_to_document(card) for card in approved],
            ids=[card.id for card in approved],
        )
        summary, _ = await compare_retrieval(
            cards,
            cases,
            ChromaVectorStore(store),
            top_k=args.top_k,
            row_path=root / "rows.jsonl",
        )
        unchanged = embeddings.identity() == identity
        summary["embedding_unchanged"] = unchanged
        code_unchanged = all(
            manifest["code_hashes"][path.relative_to(PROJECT_ROOT).as_posix()]
            == digest(path.read_text(encoding="utf-8"))
            for path in source_paths
        )
        summary["code_unchanged"] = code_unchanged
        summary["valid_comparison"] = (
            summary["valid_comparison"] and unchanged and code_unchanged
        )
        save(root / "summary.json", summary)
        manifest["state"] = "completed" if summary["valid_comparison"] else "invalid"
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    except Exception as error:
        manifest.update(state="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        manifest["finished_at"] = datetime.now(UTC).isoformat()
        save(root / "manifest.json", manifest)
    return 0 if manifest["state"] == "completed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--knowledge-dir", type=Path, default=PROJECT_ROOT / "data/knowledge"
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=PROJECT_ROOT / "data/knowledge/retrieval_cases.json",
    )
    parser.add_argument(
        "--output-root", type=Path, default=PROJECT_ROOT / "data/experiments"
    )
    parser.add_argument("--top-k", type=int, choices=range(1, 21), default=5)
    parser.add_argument("--model", default="bge-m3")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
