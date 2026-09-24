"""Profile governance ablation with shared frozen or real extraction candidates."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings
from app.core.paths import PROJECT_ROOT
from app.experiments.memory import MemorySequence, compare_memory
from app.experiments.retrieval import digest
from app.providers.llm.deepseek import DeepSeekProvider


async def run(args):
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    cases = [MemorySequence.model_validate(item) for item in dataset["sequences"]]
    root = args.output_root / f"memory-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)

    def save(name, value):
        (root / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    save("dataset.json", dataset)
    paths = [
        PROJECT_ROOT / "apps/api/app/services/user_memory.py",
        PROJECT_ROOT / "apps/api/app/schemas/memory.py",
        PROJECT_ROOT / "apps/api/app/schemas/title_font.py",
        PROJECT_ROOT / "apps/api/app/providers/llm/deepseek.py",
        PROJECT_ROOT / "apps/api/app/experiments/memory.py",
        Path(__file__).resolve(),
    ]
    hashes = {}
    for path in paths:
        relative = path.relative_to(PROJECT_ROOT)
        target = root / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        hashes[relative.as_posix()] = digest(path.read_text(encoding="utf-8"))
    manifest = {
        "state": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "dataset_hash": digest(dataset),
        "dataset_kind": dataset.get("dataset_kind", "unknown"),
        "code_hashes": hashes,
        "live": args.live,
        "baseline": "Same grounded candidates, user/scope partition and explicit retraction; overwrite every candidate without kind/confirmation gating.",
        "limitations": [
            "Development examples with simulated user confirmation, not independent dialogues.",
            "Both conditions share the same extraction response; this isolates governance rules.",
            "Unmatched simulated confirmations invalidate governance attribution; exact value, quote, scope and explicit kind must match.",
            "Frozen replay does not measure real model extraction errors.",
            "This does not establish the resume's 60 groups or 12-to-3 claim.",
        ],
    }
    save("manifest.json", manifest)
    print(f"Experiment directory: {root}", flush=True)
    try:
        provider = None
        if args.live:
            settings = get_settings()
            if not settings.deepseek_api_key:
                raise ValueError(
                    "Text model is not configured; no synthetic live fallback"
                )
            provider = DeepSeekProvider(
                api_key=settings.deepseek_api_key,
                model=settings.deepseek_text_model,
                base_url=settings.deepseek_base_url,
                timeout_seconds=settings.text_model_timeout_seconds,
            )
            manifest["model"] = settings.deepseek_text_model
            save("manifest.json", manifest)
        summary, _ = await compare_memory(cases, root / "execution", provider=provider)
        summary["code_unchanged"] = all(
            hashes[path.relative_to(PROJECT_ROOT).as_posix()]
            == digest(path.read_text(encoding="utf-8"))
            for path in paths
        )
        summary["valid_governance_comparison"] &= summary["code_unchanged"]
        save("summary.json", summary)
        manifest["state"] = (
            "completed" if summary["valid_governance_comparison"] else "invalid"
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except Exception as error:
        manifest.update(state="failed", error=type(error).__name__)
        raise
    finally:
        manifest["finished_at"] = datetime.now(UTC).isoformat()
        save("manifest.json", manifest)
    return 0 if manifest["state"] == "completed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "data/evaluation/memory_development.json",
    )
    parser.add_argument(
        "--output-root", type=Path, default=PROJECT_ROOT / "data/experiments"
    )
    parser.add_argument("--live", action="store_true")
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
