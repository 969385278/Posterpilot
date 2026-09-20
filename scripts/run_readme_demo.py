"""Run one real README example through the production LangGraph executor.

Each invocation performs one explicit phase. Separate processes demonstrate
checkpoint restoration. Credentials stay in the selected local env file, and
all raw artifacts remain under the ignored data/runs directory.
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.agent.runtime import create_runtime_executor  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.schemas.brief import PosterBrief  # noqa: E402
from app.schemas.react import HumanDecision  # noqa: E402


def save(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


async def run(args: argparse.Namespace) -> None:
    directory = (ROOT / "data/runs" / args.name).resolve()
    if not directory.is_relative_to(ROOT / "data/runs"):
        raise ValueError("Demo output must stay under data/runs")
    directory.mkdir(parents=True, exist_ok=True)
    metadata_path = directory / "demo_metadata.json"
    settings = Settings(
        _env_file=args.env_file,
        data_dir=ROOT / "data",
        langgraph_checkpoint_path=directory / "checkpoints.sqlite3",
        deepgaze_timeout_seconds=180,
        rag_collection_name=args.collection,
    )
    if not settings.deepseek_api_key or not settings.ark_api_key:
        raise RuntimeError("Real model API keys must be configured locally")

    if args.phase == "initial":
        if metadata_path.exists():
            raise FileExistsError("Use a new demo name; an existing run cannot be overwritten")
        brief = PosterBrief.model_validate(load(args.brief))
        metadata = {
            "run_id": str(uuid4()),
            "started_at": datetime.now(UTC).isoformat(),
            "code_commit": args.code_commit,
            "models": {
                "text": settings.deepseek_text_model,
                "image": settings.ark_image_model,
                "vision": settings.ark_vision_model,
                "embedding": settings.ollama_embedding_model,
                "attention": "DeepGaze III",
            },
            "phases": [],
            "entrypoint": "production LangGraph executor; no browser or API route simulation",
            "rag_collection": settings.rag_collection_name,
        }
        save(directory / "brief.json", brief.model_dump(mode="json"))
        save(metadata_path, metadata)
    else:
        metadata = load(metadata_path)

    run_id = UUID(metadata["run_id"])
    agent = create_runtime_executor(settings)
    started = perf_counter()
    print(json.dumps({"phase": args.phase, "run_id": str(run_id), "status": "started"}), flush=True)
    try:
        if args.phase == "initial":
            outcome = await agent.start(brief, run_id=run_id, run_directory=directory)
        else:
            decision = (
                HumanDecision(action="finish")
                if args.phase == "finish"
                else HumanDecision.model_validate(load(args.decision))
            )
            if args.phase == "optimize" and decision.action == "finish":
                raise ValueError("Use phase finish to end the run")
            save(directory / f"{args.phase}_decision.json", decision.model_dump(mode="json"))
            outcome = await agent.resume(run_id, decision, run_directory=directory)

        save(directory / f"{args.phase}_outcome.json", outcome.model_dump(mode="json"))
        snapshot = await (await agent._ensure_graph()).aget_state(agent._config(run_id))
        state = snapshot.values
        evidence = {}
        for key in (
            "design_spec", "layout", "retrieval_generation", "retrieval_optimization",
            "evaluation_initial", "evaluation_optimized", "analysis_initial", "analysis_current",
        ):
            value = state.get(key)
            evidence[key] = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
        save(directory / f"{args.phase}_evidence.json", evidence)
        metadata["phases"].append({
            "phase": args.phase,
            "status": outcome.status,
            "seconds": round(perf_counter() - started, 2),
            "finished_at": datetime.now(UTC).isoformat(),
        })
        save(metadata_path, metadata)
        print(json.dumps(metadata["phases"][-1]), flush=True)
        print(str(directory), flush=True)
    except Exception as error:
        # Do not dump request headers, settings, or arbitrary provider bodies.
        metadata["phases"].append({"phase": args.phase, "status": "failed", "type": type(error).__name__})
        save(metadata_path, metadata)
        print(json.dumps(metadata["phases"][-1]), flush=True)
        raise RuntimeError(f"Demo phase failed: {type(error).__name__}") from None
    finally:
        await agent.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Authorize real paid model calls")
    parser.add_argument("--phase", choices=("initial", "optimize", "finish"), required=True)
    parser.add_argument("--name", required=True, help="Output folder name under data/runs")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--brief", type=Path)
    parser.add_argument("--decision", type=Path)
    parser.add_argument("--code-commit", default="unspecified")
    parser.add_argument("--collection", default="posterpilot_design_knowledge")
    args = parser.parse_args()
    if not args.live:
        parser.exit(message="No model calls made. Pass --live to execute the selected phase.\n")
    if args.phase == "initial" and args.brief is None:
        parser.error("--brief is required for initial")
    if args.phase == "optimize" and args.decision is None:
        parser.error("--decision is required for optimize")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
