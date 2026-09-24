"""Fixed development routing cases. --live runs real hybrid and all-LLM conditions."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from uuid import uuid4

from app.core.config import get_settings
from app.core.paths import PROJECT_ROOT
from app.experiments.retrieval import digest
from app.providers.llm.deepseek import DeepSeekProvider
from app.schemas.intent import IntentRequest
from app.services.intent_router import (
    IntentRouter,
    RuleIntentClassifier,
    parse_local_requirements,
)


class RecordedProvider:
    def __init__(self, provider, records):
        self.provider = provider
        self.records = records
        self.model = getattr(provider, "model", "unknown")

    async def complete_json(self, messages):
        record = {"messages": messages, "response": None, "error": None}
        self.records.append(record)
        try:
            record["response"] = await self.provider.complete_json(messages)
            return record["response"]
        except Exception as error:
            # Do not persist provider exceptions that might contain request credentials.
            record["error"] = type(error).__name__
            raise


def canonical_controls(controls):
    return {
        "locks": {item.element_id: sorted(item.properties) for item in controls.locks},
        "adjustments": {item.trait: item.direction for item in controls.adjustments},
    }


async def run(args):
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    cases = dataset["cases"]
    allowed = {"generate", "modify", "question", "clarify", "out_of_scope"}
    if not cases or len({item["id"] for item in cases}) != len(cases):
        raise ValueError("Empty dataset or duplicate IDs")
    if any(item["expected_intent"] not in allowed for item in cases):
        raise ValueError("Unknown intent label")
    root = args.output_root / f"intents-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    (root / "dataset.json").write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    source = PROJECT_ROOT / "apps/api/app/services/intent_router.py"
    (root / "intent_router.py").write_text(
        source.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (root / "evaluate_intents.py").write_text(
        Path(__file__).read_text(encoding="utf-8"), encoding="utf-8"
    )
    manifest = {
        "state": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "dataset_hash": digest(dataset),
        "dataset_kind": dataset.get("dataset_kind", "unknown"),
        "router_code_hash": digest(source.read_text(encoding="utf-8")),
        "script_hash": digest(Path(__file__).read_text(encoding="utf-8")),
        "live": args.live,
        "threshold": 0.85,
        "scope": "Intent and deterministic constraint parsing only; no actual poster modifications or run-context claims.",
        "conditions": ["rules_only", "hybrid_live", "all_llm_live"]
        if args.live
        else ["rules_only", "router_without_provider"],
        "limitations": [
            "Development set, not independently labelled or held out.",
            "Rules confidence is heuristic, not calibrated probability.",
            "No live model means no claim of fallback improvement or model-call savings.",
        ],
    }
    manifest_path = root / "manifest.json"

    def save_manifest():
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    save_manifest()
    print(f"Experiment directory: {root}", flush=True)
    rows = []
    try:
        provider = None
        if args.live:
            settings = get_settings()
            if not settings.deepseek_api_key:
                raise ValueError(
                    "Text provider key not configured; refusing fake live output"
                )
            provider = DeepSeekProvider(
                api_key=settings.deepseek_api_key,
                model=settings.deepseek_text_model,
                base_url=settings.deepseek_base_url,
                timeout_seconds=settings.text_model_timeout_seconds,
            )
            manifest["model"] = settings.deepseek_text_model
            save_manifest()
        with (root / "rows.jsonl").open("x", encoding="utf-8") as stream:
            for case in cases:
                for condition in manifest["conditions"]:
                    calls = []
                    start = perf_counter()
                    row = {
                        "id": case["id"],
                        "text": case["text"],
                        "condition": condition,
                        "expected_intent": case["expected_intent"],
                        "error": None,
                    }
                    if condition == "rules_only":
                        classified = await RuleIntentClassifier().classify(case["text"])
                        _, controls = parse_local_requirements(case["text"])
                        prediction = classified.label
                        row["classifier_confidence"] = classified.confidence
                    else:
                        runs = SimpleNamespace(
                            executor=SimpleNamespace(
                                text_provider=RecordedProvider(provider, calls)
                            )
                            if provider
                            else None,
                            data_origin="runtime",
                        )
                        router = IntentRouter(
                            runs, direct_llm=condition == "all_llm_live"
                        )
                        result = await router.resolve(IntentRequest(text=case["text"]))
                        prediction, controls = result.intent, result.controls
                        row["resolution"] = result.model_dump(mode="json")
                        if provider and result.route_method == "unavailable":
                            row["error"] = "model_resolution_unavailable"
                    row.update(
                        prediction=prediction,
                        correct=prediction == case["expected_intent"],
                        controls=canonical_controls(controls),
                        model_calls=len(calls),
                        provider_records=calls,
                        seconds=perf_counter() - start,
                    )
                    expected = case.get("expected_controls")
                    if expected:
                        expected = {
                            "locks": {
                                key: sorted(value)
                                for key, value in expected["locks"].items()
                            },
                            "adjustments": expected["adjustments"],
                        }
                    row["controls_correct"] = (
                        row["controls"] == expected if expected is not None else None
                    )
                    rows.append(row)
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                    stream.flush()
        metrics = {}
        for condition in manifest["conditions"]:
            values = [row for row in rows if row["condition"] == condition]
            controls = [row for row in values if row["controls_correct"] is not None]
            metrics[condition] = {
                "requests": len(values),
                "intent_accuracy": sum(row["correct"] for row in values) / len(values),
                "model_calls": sum(row["model_calls"] for row in values),
                "errors": sum(row["error"] is not None for row in values),
                "control_cases": len(controls),
                "exact_controls": sum(row["controls_correct"] for row in controls),
                "failed_ids": [
                    row["id"]
                    for row in values
                    if not row["correct"] or row["controls_correct"] is False
                ],
            }
        summary = {
            "metrics": metrics,
            "live_comparison_available": args.live
            and not any(row["error"] for row in rows),
            "model_call_reduction": None,
        }
        if (
            summary["live_comparison_available"]
            and metrics["all_llm_live"]["model_calls"]
        ):
            summary["model_call_reduction"] = (
                1
                - metrics["hybrid_live"]["model_calls"]
                / metrics["all_llm_live"]["model_calls"]
            )
        summary["code_unchanged"] = manifest["router_code_hash"] == digest(
            source.read_text(encoding="utf-8")
        )
        if not summary["code_unchanged"]:
            summary["live_comparison_available"] = False
            summary["model_call_reduction"] = None
        (root / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest["state"] = (
            "completed"
            if summary["code_unchanged"] and not any(row["error"] for row in rows)
            else "invalid"
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except Exception as error:
        manifest.update(state="failed", error=type(error).__name__)
        raise
    finally:
        manifest["finished_at"] = datetime.now(UTC).isoformat()
        save_manifest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "data/evaluation/intent_development.json",
    )
    parser.add_argument(
        "--output-root", type=Path, default=PROJECT_ROOT / "data/experiments"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use configured real text model for both paired conditions",
    )
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
