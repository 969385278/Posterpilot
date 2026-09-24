import re

from app.schemas.brief import PosterBrief


def personalized_brief(brief: PosterBrief, context: dict | None) -> PosterBrief:
    """Fill unspecified design preferences; never replace current facts or constraints."""
    if not brief.use_user_memory or not context or context.get("user_id") != brief.user_id:
        return brief
    preferences = context.get("preferences", {})
    payload = brief.model_dump()
    for key, field in (
        ("style", "style_preferences"),
        ("color", "color_preferences"),
        ("avoid_elements", "avoid_elements"),
    ):
        item = preferences.get(key)
        if item and not payload[field]:
            payload[field] = [
                value.strip() for value in re.split(r"[,，;；]", item["value"]) if value.strip()
            ][:8]
    for key in ("title_font", "target_audience"):
        if key == "title_font" and any("typography" in ref.aspects for ref in brief.references):
            continue
        item = preferences.get(key)
        if item and payload[key] in ("", "auto"):
            payload[key] = item["value"]
    return PosterBrief.model_validate(payload)
