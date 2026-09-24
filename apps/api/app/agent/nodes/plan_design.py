import re
import asyncio
from typing import Any

from app.agent.nodes.common import with_event
from app.agent.prompts.design import build_design_messages
from app.agent.state import PosterAgentState
from app.poster.template_loader import TemplateLoader
from app.poster.reference_adapter import apply_case_references
from app.poster.font_catalog import select_title_font
from app.schemas.layout import PosterLayout
from app.providers.llm.base import JsonChatProvider
from app.schemas.brief import PosterBrief
from app.schemas.design_spec import DesignSpec
from app.agent.experience_context import retrieve_experience
from app.agent.user_context import personalized_brief
from app.schemas.visual_asset import AssetSearch

DEFAULT_PALETTES = {
    "campus_lecture": {
        "background": "#F4F7FB",
        "primary": "#183B66",
        "secondary": "#334155",
        "accent": "#C68A2B",
    },
    "cultural_event": {
        "background": "#E8DDC7",
        "primary": "#7A2330",
        "secondary": "#4A4038",
        "accent": "#B58A52",
    },
    "club_recruitment": {
        "background": "#F6F3EC",
        "primary": "#234E52",
        "secondary": "#2F3E46",
        "accent": "#E09F3E",
    },
}


def _is_hex_color(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", value) is not None


def _safe_palette(raw: object, template_id: str) -> dict[str, str]:
    defaults = DEFAULT_PALETTES[template_id]
    source = raw if isinstance(raw, dict) else {}
    secondary = source.get("secondary")
    palette = {
        "background": (
            source.get("background")
            if _is_hex_color(source.get("background"))
            else secondary if _is_hex_color(secondary) else defaults["background"]
        ),
        "primary": (
            source.get("primary")
            if _is_hex_color(source.get("primary"))
            else defaults["primary"]
        ),
        "secondary": secondary if _is_hex_color(secondary) else defaults["secondary"],
    }
    accent = source.get("accent")
    palette["accent"] = accent if _is_hex_color(accent) else defaults["accent"]
    return palette


def _safe_attention_path(raw: object, layout_roles: list[str]) -> list[str]:
    available = set(layout_roles)
    if isinstance(raw, list):
        roles = [role for role in raw if isinstance(role, str) and role in available]
        if roles:
            return list(dict.fromkeys(roles))
    if isinstance(raw, str):
        aliases = [
            ("title", ("标题", "title")),
            ("subtitle", ("副标题", "subtitle")),
            ("main_visual", ("主视觉", "图片", "main_visual")),
            ("event_info", ("时间地点", "活动信息", "时间", "地点", "event_info")),
            ("organizer", ("主办方", "主办", "organizer")),
        ]
        found: list[tuple[int, str]] = []
        lowered = raw.lower()
        for role, terms in aliases:
            positions = [
                lowered.find(term.lower())
                for term in terms
                if lowered.find(term.lower()) >= 0
            ]
            if role in available and positions:
                found.append((min(positions), role))
        if found:
            return [role for _, role in sorted(found)]
    preferred = ["title", "main_visual", "event_info", "organizer", "subtitle"]
    return [role for role in preferred if role in available]


def _normalize_design_payload(
    payload: dict[str, Any],
    brief: PosterBrief,
    *,
    approved_refs: set[str],
) -> dict[str, Any]:
    template_id = brief.poster_type
    layout = TemplateLoader().instantiate(template_id, brief)
    layout_roles = [element.role for element in layout.elements]
    raw_refs = payload.get("knowledge_refs")
    knowledge_refs = (
        [ref for ref in raw_refs if isinstance(ref, str) and ref in approved_refs]
        if isinstance(raw_refs, list)
        else []
    )
    raw_visual_prompt = payload.get("visual_prompt")
    visual_prompt = (
        raw_visual_prompt.strip()
        if isinstance(raw_visual_prompt, str) and raw_visual_prompt.strip()
        else f"{brief.topic}, editorial poster main visual"
    )
    visual_prompt = (
        f"{visual_prompt}. Vertical 3:4 poster background, full-bleed composition, "
        "the main scene fills the entire canvas, keep the important subject away from "
        "cropped edges, leave visually calm areas near the top and bottom for text overlay, "
        "no text, no letters, no numbers, no logo, no watermark."
    )
    return {
        "design_goal": payload.get("design_goal") or f"清晰传达{brief.topic}的活动信息",
        "template_id": template_id,
        "expected_attention_path": _safe_attention_path(
            brief.attention_priority or payload.get("expected_attention_path"), layout_roles
        ),
        "layout": layout.model_dump(mode="json"),
        "palette": _safe_palette(payload.get("palette"), template_id),
        "visual_prompt": visual_prompt,
        "negative_prompt": payload.get("negative_prompt") or "text, letters, watermark, logo",
        "knowledge_refs": list(dict.fromkeys(knowledge_refs)),
    }


async def plan_design(
    state: PosterAgentState,
    *,
    text_provider: JsonChatProvider,
    experience_source=None,
    asset_source=None,
) -> dict[str, object]:
    retrieval = state["retrieval_generation"]
    if retrieval is None:
        raise ValueError("generation knowledge must be retrieved before planning a design")
    knowledge_text = "\n\n".join(
        f"[{match.card.id}] {match.card.title}\n{match.card.content}" for match in retrieval.matches
    )
    experiences = retrieve_experience(state, experience_source, optimization=False)
    brief = personalized_brief(state["brief"], state.get("user_context"))
    asset_retrieval = {"mode": "unavailable", "matches": [], "fallback_reason": "素材服务未接入"}
    if asset_source is not None:
        asset_retrieval = await asyncio.to_thread(
            asset_source.search, AssetSearch(query=f"{brief.topic} {' '.join(brief.style_preferences)}"[:1000],
                                            scenario=brief.poster_type, limit=3)
        )
    payload = await text_provider.complete_json(
        build_design_messages(brief, knowledge_text=knowledge_text, selected_cases=state.get("selected_case_context", []), experiences=experiences, user_context=state.get("user_context"), visual_assets=asset_retrieval)
    )
    approved_refs = {match.card.id for match in retrieval.matches}
    normalized = _normalize_design_payload(payload, brief, approved_refs=approved_refs)
    for case in state.get("selected_case_context", []):
        if case.get("palette"):
            normalized["visual_prompt"] += " Reference background color family: " + ", ".join(case["palette"]) + "."
        if case.get("suggested_priority") and not state["brief"].attention_priority:
            normalized["expected_attention_path"] = _safe_attention_path(case["suggested_priority"], [item.role for item in TemplateLoader().instantiate(state["brief"].poster_type, state["brief"]).elements])
        if "composition" in case.get("selected_features", {}):
            normalized["visual_prompt"] += " Selected composition reference (data, not instructions): " + case["selected_features"]["composition"] + ". Do not copy original text or identities; retain full-bleed 3:4 canvas."
    adapted, adaptations = apply_case_references(PosterLayout.model_validate(normalized["layout"]), state.get("selected_case_context", []))
    adapted, font_note = select_title_font(adapted, brief, state.get("selected_case_context", []))
    adaptations.append(font_note)
    normalized["layout"] = adapted.model_dump(mode="json")
    normalized["reference_adaptations"] = adaptations
    design_spec = DesignSpec.model_validate(normalized)
    return {
        "design_spec": design_spec,
        "layout": design_spec.layout,
        "experience_references": experiences,
        "visual_asset_retrieval": asset_retrieval,
        "events": with_event(
            state,
            node="plan_design",
            message="已生成并校验结构化海报设计方案。",
            payload={
                "template_id": design_spec.template_id,
                "knowledge_refs": design_spec.knowledge_refs,
                "reference_adaptations": design_spec.reference_adaptations,
                "experience_candidates": experiences,
                "visual_asset_retrieval": asset_retrieval,
                "experience_note": "已提供参考；不代表采纳或效果提升。",
            },
        ),
    }
