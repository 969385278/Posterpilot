"""Run fixed-input decision-card ablation; --live requires a configured text model."""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.agent.runtime import create_runtime_executor
from app.core.config import get_settings
from app.core.paths import PROJECT_ROOT
from app.experiments.decisions import DecisionTask, compare_decisions, save
from app.experiments.retrieval import digest
from app.persistence.database import Database
from app.persistence.datahub_repository import DataHubRepository
from app.services.datahub_service import DataHubService
from app.services.decision_cards import DecisionCardService
from app.services.tool_harness import ToolHarness


class SharedRetrieval:
    """Repeated identical requests share the same real retrieval response across arms."""

    def __init__(self, source, root):
        self.source, self.root, self.cache = source, root, {}

    async def retrieve(self, request):
        key = digest(request.model_dump(mode="json"))
        if key not in self.cache:
            result = await self.source.retrieve(request)
            save(
                self.root / f"retrieval_{key}.json",
                {
                    "request": request.model_dump(mode="json"),
                    "response": result.model_dump(mode="json"),
                },
            )
            if result.error:
                raise RuntimeError(
                    "Experiment retrieval unavailable; see recorded response"
                )
            self.cache[key] = result
        return self.cache[key].model_copy(deep=True)


def source_files():
    paths = list((PROJECT_ROOT / "apps/api/app").rglob("*.py"))
    for name in ["templates", "fonts", "knowledge"]:
        paths.extend(
            path for path in (PROJECT_ROOT / "data" / name).rglob("*") if path.is_file()
        )
    return sorted(
        {
            *paths,
            Path(__file__).resolve(),
            Path(__file__).with_name("evaluate_capabilities.py").resolve(),
        }
    )


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def run(args):
    intervention = args.intervention
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    tasks = []
    for value in dataset["tasks"]:
        task = DecisionTask.model_validate(value)
        if not task.main_visual.is_absolute():
            task.main_visual = (args.dataset.parent / task.main_visual).resolve()
        tasks.append(task)
    prefix = "capabilities" if intervention == "tools" else "decisions"
    root = args.output_root / f"{prefix}-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    save(root / "dataset.json", dataset)
    manifest = {
        "state": "preflight",
        "started_at": datetime.now(UTC).isoformat(),
        "dataset_kind": dataset.get("dataset_kind", "unknown"),
        "dataset_hash": digest(dataset),
        "live": args.live,
        "intervention": intervention,
        "added_tools": args.added_tools,
        "limitations": [
            (
                "Only tool availability changes; decision cards are disabled in both arms."
                if intervention == "tools"
                else "Only decision-card context changes; ordinary experience remains in both arms."
            ),
            "Rule-only evaluation; no vision model or attention-quality claims.",
            "Bounded three-tool rounds, unresolved outcomes reported as censored.",
            "No claim of independent held-out data or the resume's numerical gains.",
            "A single paired run does not control sampling variance or backend model drift.",
            "Added tools do not imply new expressive capability; alignment is also possible with modify_layout.",
        ],
    }
    save(root / "manifest.json", manifest)
    print(f"Experiment directory: {root}", flush=True)
    database = None
    executor = None
    try:
        if intervention == "tools" and not args.added_tools:
            raise ValueError(
                "Specify --added-tools with already-published extension names"
            )
        if not args.live:
            raise ValueError(
                "Specify --live to call the configured model; no fixture benchmark fallback"
            )
        settings = get_settings()
        if not settings.deepseek_api_key:
            raise ValueError("Text model is not configured; no synthetic live fallback")
        paths = source_files()
        hashes = {}
        for path in paths:
            relative = path.relative_to(PROJECT_ROOT)
            target = root / "source" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            hashes[relative.as_posix()] = file_hash(target)
        manifest.update(
            state="running",
            model=settings.deepseek_text_model,
            model_base_url=settings.deepseek_base_url,
            code_and_data_hashes=hashes,
            dependencies={
                name: importlib.metadata.version(name)
                for name in ["pydantic", "Pillow", "langgraph", "httpx"]
            },
        )
        save(root / "manifest.json", manifest)
        database = Database(settings.database_url)
        hub = DataHubService(
            DataHubRepository(database), settings.data_dir / "datahub-assets"
        )
        hub.decisions = DecisionCardService(hub)
        cases = hub.repository.list()
        cards = hub.decisions.repository.list()
        evaluation_runs = {task.source_run_id for task in tasks}
        if any(
            case.status == "approved" and case.run_id in evaluation_runs
            for case in cases
        ):
            raise ValueError(
                "Evaluation source runs occur in approved ordinary experience"
            )
        if any(
            card.status == "approved" and card.source_run_id in evaluation_runs
            for card in cards
        ):
            raise ValueError(
                "Evaluation source runs occur in approved decision-card training evidence"
            )
        save(root / "hub_cases.json", [case.model_dump(mode="json") for case in cases])
        save(
            root / "decision_cards.json",
            [card.model_dump(mode="json") for card in cards],
        )
        executor = create_runtime_executor(settings)
        executor.tools.retriever = SharedRetrieval(executor.retriever, root)
        executor.tools.release_source = ToolHarness(
            settings.data_dir / "tool-harness", hub
        )
        summary, _ = await compare_decisions(
            tasks,
            root / "execution",
            provider=executor.text_provider,
            tools=executor.tools,
            hub=hub,
            live=True,
            rounds=args.rounds,
            intervention=intervention,
            added_tools=args.added_tools,
        )
        summary["code_and_data_unchanged"] = paths == source_files() and all(
            file_hash(path) == hashes[path.relative_to(PROJECT_ROOT).as_posix()]
            for path in paths
        )
        summary["valid_live_comparison"] &= summary["code_and_data_unchanged"]
        save(root / "summary.json", summary)
        manifest["state"] = (
            "completed" if summary["valid_live_comparison"] else "invalid"
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except Exception as error:  # noqa: BLE001 - CLI persists failure state for every runtime error.
        manifest.update(state="failed", error_type=type(error).__name__)
        print(str(error), flush=True)
    finally:
        if executor:
            await executor.aclose()
        if database:
            database.engine.dispose()
        manifest["finished_at"] = datetime.now(UTC).isoformat()
        save(root / "manifest.json", manifest)
    return 0 if manifest["state"] == "completed" else 1


def main(*, intervention="cards"):
    parser = argparse.ArgumentParser(
        description=(
            "Compare original tools with already-published extensions using fixed inputs."
            if intervention == "tools"
            else __doc__
        )
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument(
        "--output-root", type=Path, default=PROJECT_ROOT / "data/experiments"
    )
    parser.add_argument("--rounds", type=int, choices=[1, 2, 3], default=3)
    parser.add_argument("--live", action="store_true")
    parser.set_defaults(intervention=intervention)
    parser.add_argument("--added-tools", nargs="+", default=[])
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
