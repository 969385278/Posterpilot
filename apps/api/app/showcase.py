"""Reviewed public-domain images + fixed decisions, never production model replacements."""

import base64
import hashlib
import html
import json
import re
from pathlib import Path

from app.core.paths import PROJECT_ROOT
from app.demo import create_demo_app
from app.providers.image.base import GeneratedImage
from app.rag.models import RetrievalMatch, RetrievalResult
from app.rag.repository import KnowledgeRepository
from app.rag.reranker import lexical_similarity


def reviewed_media() -> dict[str, dict]:
    root = PROJECT_ROOT / "data/media"
    selection = json.loads((root / "reviewed_media.json").read_text(encoding="utf-8"))
    result = {}
    for asset in selection["assets"]:
        key = f"commons-{asset['page_id']}"
        source = json.loads((root / "sources" / f"{key}.json").read_text(encoding="utf-8"))
        info = source["response"]["imageinfo"][0]
        metadata = info["extmetadata"]
        if metadata["LicenseShortName"]["value"] != "Public domain":
            raise ValueError(f"Showcase background requires a reviewed public-domain source: {key}")
        image = root / "images" / source["image_asset"]
        if hashlib.sha256(image.read_bytes()).hexdigest() != source["image_sha256"]:
            raise ValueError(f"Media hash mismatch: {key}")
        creator = html.unescape(re.sub(r"<[^>]+>", "", metadata["Artist"]["value"])).strip()
        result[asset["id"]] = {
            **asset,
            "path": image,
            "creator": creator,
            "source_url": info["descriptionurl"],
            "rights": "Public domain（来源页标注）",
            "rights_url": info["descriptionurl"] + "#Licensing",
            "sha256": source["image_sha256"],
            "retrieved_at": source["retrieved_at"],
        }
    return result


class ShowcaseImageProvider:
    async def generate(self, prompt, *, size=None, reference_image_url=""):
        marker = re.search(r"reviewed-media:([a-z]+)", prompt)
        if marker is None:
            raise ValueError("Showcase requires an explicit reviewed media ID")
        asset = reviewed_media()[marker[1]]
        raw = asset["path"].read_bytes()
        return GeneratedImage(
            image_url="data:image/jpeg;base64," + base64.b64encode(raw).decode(),
            provider="reviewed-public-domain-image",
            model=asset["id"],
        )


class ShowcaseTextProvider:
    """Fixed demo choices; no model call, no fabricated autonomous reasoning."""

    async def complete_json(self, messages):
        if "ReAct Agent" not in messages[0]["content"]:
            brief = json.loads(
                messages[-1]["content"].split("活动事实：", 1)[1].split("\n\n", 1)[0]
            )
            selected = {
                "cultural_event": "irises",
                "campus_lecture": "nebula",
                "club_recruitment": "tetons",
            }
            return {
                "design_goal": "授权素材排版演示；固定规划，不代表在线大模型生成",
                "visual_prompt": f"reviewed-media:{selected[brief['poster_type']]}",
                "knowledge_refs": [],
            }
        context = json.loads(messages[-1]["content"])
        traces = context["recent_tool_observations"]
        event = next(
            (
                item
                for item in context["current_layout"]["elements"]
                if item["role"] == "event_info"
            ),
            None,
        )
        if not traces and event:
            return {
                "decision": "tool_call",
                "summary": "固定演示方案：放大时间地点，随后实际渲染复评。",
                "tool_name": "modify_typography",
                "arguments": {
                    "actions": [
                        {
                            "action": "set_font_size",
                            "target_id": event["id"],
                            "parameters": {"font_size": 42},
                            "reason": "展示活动信息排版调整，不伪装模型推理",
                        }
                    ]
                },
            }
        return {
            "decision": "finish_round",
            "summary": "固定演示动作结束，交由真实渲染器与评测模块处理。",
        }


class ShowcaseRetriever:
    async def retrieve(self, request):
        cards = KnowledgeRepository(PROJECT_ROOT / "data/knowledge").approved_cards()
        ranked = sorted(
            (
                (lexical_similarity(c, request.query), c)
                for c in cards
                if request.intent in c.intents
            ),
            key=lambda item: -item[0],
        )
        matches = [
            RetrievalMatch(card=c, similarity=score, vector_similarity=0, lexical_similarity=score)
            for score, c in ranked[:3]
            if score > 0
        ]
        return RetrievalResult(
            query=request.query,
            matches=matches,
            fallback_reason="showcase_lexical_only_not_vector_search",
        )


def create_app(data_root: Path | None = None):
    return create_demo_app(
        data_root or PROJECT_ROOT / "data/reviewed-showcase",
        text_provider=ShowcaseTextProvider(),
        image_provider=ShowcaseImageProvider(),
        retriever=ShowcaseRetriever(),
    )
