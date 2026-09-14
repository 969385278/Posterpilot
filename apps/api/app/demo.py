"""Explicit offline demo factory; never selected by the production runtime.

Run: python -m uvicorn app.demo:create_demo_app --factory --app-dir apps/api --port 8790
Model decisions and artwork are deterministic fixtures, not quality evidence.
"""

import asyncio
import base64
import json
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from app.agent.executor import LangGraphAgentExecutor
from app.agent.nodes.evaluate import EvaluationDependencies
from app.core.paths import PROJECT_ROOT
from app.evaluation.deepgaze_client import DeepGazePrediction
from app.main import create_app
from app.persistence.run_repository import RunRepository
from app.poster.renderer import PosterRenderer
from app.providers.image.base import GeneratedImage
from app.rag.models import RetrievalResult
from app.schemas.evaluation import AttentionPrediction, Fixation
from app.services.artifact_service import ArtifactService
from app.services.event_bus import EventBus
from app.services.run_service import RunService


class DemoRetriever:
    async def retrieve(self, request):
        return RetrievalResult(
            query=request.query,
            fallback_reason="offline_demo_no_external_retrieval",
        )


class DemoTextProvider:
    async def complete_json(self, messages):
        await asyncio.sleep(0.5)
        if "ReAct Agent" not in messages[0]["content"]:
            return {
                "design_goal": "离线演示：完整验证生成与人工优化流程",
                "visual_prompt": "offline geometric artwork",
                "knowledge_refs": [],
            }
        context = json.loads(messages[-1]["content"])
        traces = context["recent_tool_observations"]
        controls = context.get("design_controls", {})
        adjustments = controls.get("adjustments", [])
        background = {item["trait"]: item for item in adjustments if item["trait"] in {"background_contrast", "background_saturation"} and item["direction"] != "preserve"}
        if background and not any(trace["tool_name"] == "adjust_background" for trace in traces):
            treatment = context.get("current_background_treatment", {})
            arguments = {}
            for trait, item in background.items():
                parameter = "contrast" if trait == "background_contrast" else "saturation"
                multiplier = 1 + item["strength"] * (1 if item["direction"] == "strengthen" else -1)
                arguments[parameter] = max(0.35 if parameter == "contrast" else 0, min(1.65, treatment.get(parameter, 1) * multiplier))
            return {"decision": "tool_call", "summary": "离线演示：按所选方向处理背景（固定规则，不是模型推理）", "tool_name": "adjust_background", "arguments": arguments}
        emphasis = next((item for item in adjustments if item["trait"] == "title_emphasis" and item["direction"] != "preserve"), None)
        if emphasis and not any(trace["tool_name"] == "modify_typography" for trace in traces):
            title = next(item for item in context["current_layout"]["elements"] if item["role"] == "title")
            scale = 1 + emphasis["strength"] * (1 if emphasis["direction"] == "strengthen" else -1)
            return {"decision": "tool_call", "summary": "离线演示：按所选方向调整标题字号", "tool_name": "modify_typography", "arguments": {"actions": [{"action": "set_font_size", "target_id": title["id"], "parameters": {"font_size": max(10, min(240, round(title["font_size"] * scale)))}, "reason": "固定演示规则"}]}}
        if adjustments or controls.get("locks") or controls.get("attention_priority"):
            return {"decision": "finish_round", "summary": "离线演示：结构化要求已处理；锁定冲突由执行器拒绝，结果由渲染后验证。"}
        if not traces:
            return {
                "decision": "tool_call",
                "summary": "离线演示：先检查设计知识链路",
                "tool_name": "search_design_knowledge",
                "arguments": {"query": "活动信息可读性", "target_roles": ["event_info"]},
            }
        if len(traces) == 1:
            return {
                "decision": "tool_call",
                "summary": "离线演示：调整时间地点字号",
                "tool_name": "modify_typography",
                "arguments": {
                    "actions": [
                        {
                            "action": "set_font_size",
                            "target_id": "event_info",
                            "parameters": {"font_size": 52},
                            "reason": "固定演示动作，不是模型推理",
                        }
                    ]
                },
            }
        return {"decision": "finish_round", "summary": "离线演示：统一渲染并复评"}


class DemoImageProvider:
    def __init__(self, *, fail: bool = False):
        self.fail = fail

    async def generate(self, prompt, *, size=None, reference_image_url=""):
        await asyncio.sleep(1)
        if self.fail:
            raise RuntimeError("离线演示：主动注入生图失败，用于验证错误页面。")
        # Procedural test fixture, not an externally generated or edited image.
        canvas = Image.new("RGB", (1080, 1440), "#E7EBE5")
        draw = ImageDraw.Draw(canvas)
        draw.ellipse((220, 280, 1130, 1190), fill="#B4C8B5")
        draw.ellipse((-160, 600, 570, 1330), fill="#739487")
        draw.rounded_rectangle((300, 570, 810, 930), radius=45, fill="#224C4B")
        draw.ellipse((400, 605, 710, 915), fill="#DBB76B")
        draw.ellipse((450, 655, 660, 865), fill="#335D58")
        data = BytesIO()
        canvas.save(data, format="PNG")
        return GeneratedImage(
            image_url="data:image/png;base64," + base64.b64encode(data.getvalue()).decode(),
            provider="offline-demo",
            model="procedural-fixture",
        )


class DemoAttentionClient:
    """Synthetic contract fixture, never a DeepGaze inference implementation."""

    async def predict(self, *, image_bytes, filename="poster.png", steps=5):
        canvas = Image.new("RGB", (384, 512), "#172340")
        draw = ImageDraw.Draw(canvas)
        points = [(0.5, 0.16), (0.5, 0.5), (0.5, 0.82)]
        for index, (x, y) in enumerate(points):
            cx, cy = int(x * canvas.width), int(y * canvas.height)
            draw.ellipse((cx - 40, cy - 40, cx + 40, cy + 40), fill="#EFA958")
            draw.text((cx - 4, cy - 5), str(index + 1), fill="black")
        draw.text((16, 480), "TEST FIXTURE - NOT DEEPGAZE", fill="white")
        buffer = BytesIO()
        canvas.save(buffer, format="PNG")
        return DeepGazePrediction(
            availability="available",
            attention=AttentionPrediction(
                availability="available",
                model="offline-demo-synthetic-attention",
                device="fixture",
                fixations=[
                    Fixation(x=x, y=y, order=index + 1)
                    for index, (x, y) in enumerate(points[:steps])
                ],
            ),
            heatmap_png=buffer.getvalue(),
        )


def create_demo_app(
    data_root: Path | None = None, *, fail_image: bool = False, synthetic_attention: bool = False
):
    root = (data_root or PROJECT_ROOT / "data" / "offline-demo").resolve()
    root.mkdir(parents=True, exist_ok=True)
    service = RunService(
        repository=RunRepository(f"sqlite:///{(root / 'runs.sqlite3').as_posix()}"),
        artifacts=ArtifactService(root / "runs"),
        event_bus=EventBus(),
        executor=LangGraphAgentExecutor(
            retriever=DemoRetriever(),
            text_provider=DemoTextProvider(),
            image_provider=DemoImageProvider(fail=fail_image),
            renderer=PosterRenderer(),
            checkpoint_path=root / "checkpoints.sqlite3",
            evaluation=EvaluationDependencies(
                deepgaze=DemoAttentionClient() if synthetic_attention else None,
            ),
        ),
    )
    app = create_app(run_service=service)
    app.title = "PosterPilot OFFLINE DEMO — deterministic fixtures"
    return app


def create_heatmap_demo_app():
    """Opt-in UI acceptance factory with separate data and visibly marked fixture."""
    return create_demo_app(
        PROJECT_ROOT / "data" / "offline-heatmap-demo", synthetic_attention=True
    )
