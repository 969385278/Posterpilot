"""Choose readable initial text colors after the actual background is available.

Never applied during edits: later exact colors, opacity goals and typography locks
remain authoritative. This is a sampled contrast heuristic, not a quality guarantee.
"""

from app.evaluation.readability import readability_background, sampled_text_contrast
from app.schemas.design_control import DesignControls


def _adapt_colors_for_background(
    layout, *, palette, main_visual_path, treatment, text_facts, controls: DesignControls
):
    background = readability_background(layout, main_visual_path, treatment)
    updated = layout.model_copy(deep=True)
    elements = {element.id: element for element in updated.elements}
    locked = {lock.element_id for lock in controls.locks if "typography" in lock.properties}
    changes = []
    for fact in text_facts:
        if fact.element_id in locked:
            continue
        before = sampled_text_contrast(background, fact)
        threshold = 3.0 if fact.actual_font_size >= 24 else 4.5
        if before is None or before >= threshold:
            continue
        element = elements[fact.element_id]
        preferred = (
            [palette.primary, palette.secondary]
            if element.role == "title"
            else [
                palette.secondary,
                palette.primary,
            ]
        )
        candidates = list(dict.fromkeys([*preferred, "#111827", "#F8FAFC", "#000000", "#FFFFFF"]))
        scored = [
            (color, sampled_text_contrast(background, fact.model_copy(update={"color": color})))
            for color in candidates
        ]
        eligible = [(color, ratio) for color, ratio in scored if ratio is not None]
        if not eligible:
            continue
        # Prefer the first sufficiently readable palette color; otherwise use
        # the best measured fallback, retaining failures in the final evaluation.
        color, ratio = next(
            ((c, r) for c, r in eligible if r >= threshold), max(eligible, key=lambda item: item[1])
        )
        if ratio <= before:
            continue
        element.color = color
        changes.append(
            {
                "element_id": element.id,
                "before_color": fact.color,
                "after_color": color,
                "before_contrast": round(before, 3),
                "after_contrast": round(ratio, 3),
                "threshold": threshold,
            }
        )
    return updated, changes


def adapt_initial_text_colors(
    layout, *, palette, main_visual_path, treatment, text_facts, controls: DesignControls
):
    def candidate(source):
        updated, changes = _adapt_colors_for_background(
            source,
            palette=palette,
            main_visual_path=main_visual_path,
            treatment=treatment,
            text_facts=text_facts,
            controls=controls,
        )
        background = readability_background(updated, main_visual_path, treatment)
        colors = {element.id: element.color for element in updated.elements}
        failed = 0
        for fact in text_facts:
            ratio = sampled_text_contrast(
                background,
                fact.model_copy(
                    update={"color": colors[fact.element_id] or "#F8FAFC"},
                ),
            )
            failed += ratio is None or ratio < (3.0 if fact.actual_font_size >= 24 else 4.5)
        return updated, changes, failed

    selected = candidate(layout)
    if layout.readability_scrims and not controls.has_request:
        alternate = candidate(layout.model_copy(update={"readability_scrims": False}))
        # Change the background treatment only when it resolves additional failures.
        # Keep the selected mode in the layout so later rounds never switch silently.
        if alternate[2] < selected[2]:
            selected = alternate
    return selected[0], selected[1]
