"""Small live experiment; real paid APIs only when --live is specified.

Each brief uses two background generations (no case / selected case), one
bounded Agent optimization, and one direct image edit of the same initial
poster. Attention ablation reranks the same rendered candidates, not new images.
Never substitutes demo/fixture output for a failed real model.
"""
import argparse
import asyncio
import base64
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import httpx
from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
from app.agent.executor import LangGraphAgentExecutor
from app.agent.nodes.evaluate import EvaluationDependencies
from app.agent.tools.generation_tools import materialize_generated_image
from app.core.config import Settings
from app.evaluation.deepgaze_client import DeepGazeClient
from app.evaluation.vision_evaluator import VisionEvaluator
from app.poster.renderer import PosterRenderer
from app.providers.image.ark import ArkImageProvider
from app.providers.image.base import GeneratedImage
from app.providers.llm.deepseek import DeepSeekProvider
from app.providers.vision.ark import ArkVisionProvider
from app.rag.models import RetrievalResult
from app.schemas.brief import PosterBrief
from app.schemas.react import HumanDecision


class NoPrinciples:
    """Hold principle retrieval absent in every condition to isolate case effects.

    This is an explicitly disabled experimental variable, not a fake RAG result.
    """
    async def retrieve(self, request):
        return RetrievalResult(query=request.query, fallback_reason="experiment_principles_disabled_in_all_conditions")


class RecordedText:
    def __init__(self, provider, directory):
        self.provider, self.directory, self.calls = provider, directory, 0

    async def complete_json(self, messages):
        self.calls += 1
        start = perf_counter()
        result = await self.provider.complete_json(messages)
        save(self.directory / f"text_call_{self.calls}.json", {"messages": messages, "response": result, "seconds": perf_counter() - start})
        return result


def save(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def pixels(path: Path):
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        return {"width": image.width, "height": image.height,
                "whole_poster_luminance_std": ImageStat.Stat(rgb.convert("L")).stddev[0] / 255,
                "whole_poster_mean_saturation": ImageStat.Stat(rgb.convert("HSV").getchannel("S")).mean[0] / 255,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def attention_ablation(checkpoint):
    candidates = checkpoint.layout_candidates
    results = []
    for candidate in candidates:
        readability = [item for item in candidate.checks if item.key.startswith("readability:")]
        rules = [item for item in candidate.checks if not item.key.startswith("readability:") and item.status != "unavailable"]
        base = 100 * (0.65 * sum(item.status == "passed" for item in readability) / max(1, len(readability))
                      + 0.35 * sum(item.status == "passed" for item in rules) / max(1, len(rules)))
        results.append({"id": candidate.id, "label": candidate.label, "current": candidate.is_current,
                        "with_attention": candidate.rank_score, "without_attention": round(base, 2),
                        "attention_used": candidate.attention_used_for_ranking,
                        "predicted_path": candidate.attention.predicted_path,
                        "subject_overlap": candidate.subject_overlap})
    with_attention = sorted(results, key=lambda item: (-item["with_attention"], not item["current"], item["id"]))
    without = sorted(results, key=lambda item: (-item["without_attention"], not item["current"], item["id"]))
    return {"candidates": results, "with_attention_top": with_attention[0]["id"] if with_attention else None,
            "without_attention_top": without[0]["id"] if without else None,
            "without_attention_tied_top": [item["id"] for item in without if item["without_attention"] == without[0]["without_attention"]] if without else [],
            "tie_break": "higher score, then current layout, then stable candidate ID; independent of input ordering",
            "valid_comparison": bool(len(results) >= 2 and all(item["attention_used"] for item in results)),
            "limit": "Same rendered candidates; isolates ranking contribution only. Not aesthetic improvement, user study, or full autoregressive scanpath."}


async def direct_edit(settings, original: Path, directory: Path, instruction: str):
    # Send a PNG data URL explicitly. Never drop the reference on failure and
    # silently substitute an unrelated text-to-image baseline.
    with Image.open(original) as image:
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="PNG")
    payload = {"model": settings.ark_image_model, "prompt": instruction,
               "image": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(),
               "size": settings.ark_image_size, "response_format": "b64_json"}
    save(directory / "direct_edit_request.json", {key: value for key, value in payload.items() if key != "image"} | {"reference_sha256": hashlib.sha256(original.read_bytes()).hexdigest()})
    start = perf_counter()
    async with httpx.AsyncClient(timeout=settings.image_model_timeout_seconds) as client:
        response = await client.post(settings.ark_base_url.rstrip("/") + "/images/generations", headers={"Authorization": f"Bearer {settings.ark_api_key}"}, json=payload)
    if response.is_error:
        raise RuntimeError(f"Direct image edit HTTP {response.status_code}; reference was not dropped")
    item = response.json()["data"][0]
    image_url = item.get("url") or "data:image/png;base64," + item["b64_json"]
    output = await materialize_generated_image(GeneratedImage(image_url=image_url, provider="ark-direct-edit", model=settings.ark_image_model), output_path=directory / "direct_edit.png")
    return {"seconds": perf_counter() - start, "image": str(output), "pixels": pixels(output),
            "exact_text_and_layout_preservation": "unverified_flat_image_requires_visual_or_OCR_review",
            "reference_fallback": False}


async def run_one(settings, root: Path, name: str, brief: PosterBrief):
    data = {"brief": brief.model_dump(mode="json"), "conditions": {}, "errors": []}
    image_provider = ArkImageProvider(api_key=settings.ark_api_key, model=settings.ark_image_model,
        base_url=settings.ark_base_url, default_size=settings.ark_image_size,
        response_format=settings.ark_image_response_format, timeout_seconds=settings.image_model_timeout_seconds)
    vision = VisionEvaluator(ArkVisionProvider(api_key=settings.ark_api_key, model=settings.ark_vision_model,
        base_url=settings.ark_base_url, timeout_seconds=settings.vision_model_timeout_seconds))
    for condition in ("no_case", "selected_case"):
        directory = root / name / condition
        directory.mkdir(parents=True, exist_ok=True)
        text = RecordedText(DeepSeekProvider(api_key=settings.deepseek_api_key, model=settings.deepseek_text_model,
            base_url=settings.deepseek_base_url, timeout_seconds=settings.text_model_timeout_seconds), directory)
        agent = LangGraphAgentExecutor(retriever=NoPrinciples(), text_provider=text, image_provider=image_provider,
            renderer=PosterRenderer(), checkpoint_path=directory / "checkpoints.sqlite3",
            evaluation=EvaluationDependencies(deepgaze=DeepGazeClient(base_url=settings.deepgaze_base_url, timeout_seconds=180), vision=vision))
        run_id = uuid4()
        current_brief = brief.model_copy(update={"references": []}) if condition == "no_case" else brief
        record = {"run_id": str(run_id), "status": "started"}
        data["conditions"][condition] = record
        start = perf_counter()
        try:
            outcome = await agent.start(current_brief, run_id=run_id, run_directory=directory)
            checkpoint = outcome.checkpoint
            save(directory / "initial_checkpoint.json", checkpoint.model_dump(mode="json"))
            state = (await (await agent._ensure_graph()).aget_state(agent._config(run_id))).values
            save(directory / "design_spec.json", state["design_spec"].model_dump(mode="json"))
            record.update(status="initial_completed", initial_seconds=perf_counter() - start,
                          initial_pixels=pixels(directory / "poster_initial.png"), attention_ablation=attention_ablation(checkpoint),
                          vision=state["evaluation_initial"].vision.model_dump(mode="json"))
            if condition == "selected_case":
                decision = HumanDecision.model_validate({"action": "instruct", "instruction": "只减弱背景明暗反差约20%，保持所有文字内容、位置和样式不变，不改变主视觉内容。",
                    "controls": {"adjustments": [{"trait": "background_contrast", "direction": "weaken", "strength": 0.2}],
                                 "locks": [{"element_id": element["id"], "properties": ["position", "typography"]} for element in checkpoint.layout["elements"] if element.get("content")]}})
                save(directory / "human_decision.json", decision.model_dump(mode="json"))
                optimize_start = perf_counter()
                optimized = await agent.resume(run_id, decision, run_directory=directory)
                save(directory / "optimized_checkpoint.json", optimized.checkpoint.model_dump(mode="json"))
                record["agent_optimization"] = {"seconds": perf_counter() - optimize_start,
                    "pixels": pixels(directory / "poster_round_1.png"), "verification": optimized.checkpoint.goal_verification.model_dump(mode="json"),
                    "tool_traces": [trace.model_dump(mode="json") for trace in optimized.checkpoint.tool_traces]}
                try:
                    record["direct_edit"] = await direct_edit(settings, directory / "poster_initial.png", directory, decision.instruction)
                except Exception as error:
                    record["direct_edit"] = {"status": "failed", "error_type": type(error).__name__, "detail": str(error).replace(settings.ark_api_key, "[redacted]")}
            final = await agent.resume(run_id, HumanDecision(action="finish"), run_directory=directory)
            save(directory / "result.json", final.result)
            record["status"] = "completed"
        except Exception as error:
            # Provider classes redact keys. Do not record arbitrary raw network bodies.
            record.update(status="failed", error_type=type(error).__name__)
            data["errors"].append({"condition": condition, "error_type": type(error).__name__})
        finally:
            await agent.aclose()
            save(root / name / "summary.json", data)
            print(json.dumps({"experiment": name, "condition": condition, "status": record["status"], "error_type": record.get("error_type")}), flush=True)
    return data


async def main(args):
    settings = Settings()
    if not settings.deepseek_api_key or not settings.ark_api_key:
        raise RuntimeError("Real-model API keys are not configured")
    root = ROOT / "data/experiments" / datetime.now(timezone.utc).strftime("controlled-design-%Y%m%dT%H%M%SZ")
    cases = [("club", PosterBrief.model_validate({"poster_type": "club_recruitment", "topic": "摄影社招新", "target_audience": "大学生", "title": "摄影社招新", "subtitle": "用镜头记录校园", "event_time": "2026年9月20日 18:30", "location": "学生活动中心一楼", "organizer": "摄影社", "style_preferences": ["简洁", "竖版", "背景铺满画面"], "visual_elements": ["相机", "校园傍晚"], "references": [{"case_id": "commons-24204726", "aspects": ["palette", "typography", "composition"]}]}))]
    if args.briefs == 2:
        cases.append(("swim", PosterBrief.model_validate({"poster_type": "club_recruitment", "topic": "游泳社体验课", "target_audience": "大学生", "title": "游泳社体验课", "event_time": "2026年9月21日 15:00", "location": "校游泳馆", "organizer": "游泳社", "style_preferences": ["简洁", "运动感"], "visual_elements": ["泳池", "跳水板"], "references": [{"case_id": "commons-31912550", "aspects": ["palette", "typography", "hierarchy"]}]})))
    manifest = {"started_at": datetime.now(timezone.utc).isoformat(), "models": {"text": settings.deepseek_text_model, "image": settings.ark_image_model, "vision": settings.ark_vision_model, "attention": "DeepGaze III rgb255-v2"},
                "limits": ["Small exploratory sample, no statistical improvement claims", "Principle retrieval disabled in all conditions", "Case conditions use independent stochastic backgrounds; differences are not causal quality evidence", "Direct editor receives the same initial poster and instruction, no silent reference fallback", "Attention ablation reuses identical candidates; peak ordering proxy, not true gaze tracking", "Failures and unavailable signals retained; no synthetic replacement"], "results": []}
    save(root / "manifest.json", manifest)
    print(str(root), flush=True)
    for name, brief in cases:
        manifest["results"].append(await run_one(settings, root, name, brief))
        save(root / "manifest.json", manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Execute configured real paid model calls")
    parser.add_argument("--briefs", type=int, choices=[1, 2], default=1)
    args = parser.parse_args()
    if not args.live:
        parser.exit(message="No API calls made. Use --live to run 2 image generations + 1 direct edit per brief, plus bounded text/vision calls.\n")
    asyncio.run(main(args))
