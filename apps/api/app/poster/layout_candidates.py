"""Bounded candidate layouts. Models do not supply arbitrary executable geometry."""

from app.poster.design_guards import DesignConstraintError, assert_design_constraints
from app.schemas.design_control import DesignControls
from app.schemas.layout import NormalizedBox, PosterLayout


def propose_layouts(layout: PosterLayout, controls: DesignControls, subject_regions: list[NormalizedBox] | None = None) -> list[tuple[str, PosterLayout]]:
    variants = []
    seen = {layout.model_dump_json()}
    locked = {lock.element_id for lock in controls.locks if "position" in lock.properties}
    for label, title_y, detail_y in (
        ("上方标题 · 下方信息", 0.06, 0.72),
        ("中段标题 · 下方信息", 0.35, 0.72),
        ("上方信息 · 下方标题", 0.63, 0.06),
        ("上方标题 · 中段信息", 0.06, 0.44),
    ):
        candidate = layout.model_copy(deep=True)
        valid = True
        for roles, start in ((["title", "subtitle"], title_y), (["event_info", "organizer"], detail_y)):
            y = start
            for role in roles:
                for element in [item for item in candidate.elements if item.role == role]:
                    if element.id in locked:
                        y = element.box.y + element.box.height + 0.018
                        continue
                    if y + element.box.height > 0.97:
                        valid = False
                        break
                    element.box = NormalizedBox(x=element.box.x, y=y, width=element.box.width, height=element.box.height)
                    y += element.box.height + 0.018
        if not valid or candidate.model_dump_json() in seen:
            continue
        try:
            assert_design_constraints(layout, candidate, controls)
        except DesignConstraintError:
            continue
        seen.add(candidate.model_dump_json())
        variants.append((label, candidate))
    # For a tall central subject, moving information only up/down may leave
    # every candidate obstructed. Try the actual side bands outside estimated
    # subject boxes. Do not move the image or shrink text without render checks.
    if subject_regions:
        left = min(box.x for box in subject_regions)
        right = max(box.x + box.width for box in subject_regions)
        bands = [("主体左侧信息", 0.04, min(0.4, left - 0.075)),
                 ("主体右侧信息", right + 0.035, min(0.4, 0.925 - right))]
        for label, x, width in bands:
            if width < 0.22:
                continue
            candidate = layout.model_copy(deep=True)
            changed = False
            for element in candidate.elements:
                if element.role not in {"event_info", "organizer"} or element.id in locked:
                    continue
                element.box = NormalizedBox(x=x, y=element.box.y, width=width, height=element.box.height)
                changed = True
            if not changed or candidate.model_dump_json() in seen:
                continue
            try:
                assert_design_constraints(layout, candidate, controls)
            except DesignConstraintError:
                continue
            seen.add(candidate.model_dump_json())
            variants.append((label, candidate))
    return variants


def subject_overlap_ratio(boxes: list[dict[str, int]], subjects: list[NormalizedBox], layout: PosterLayout) -> float | None:
    if not subjects:
        return None
    overlaps = []
    for subject in subjects:
        covered = 0.0
        for box in boxes:
            x, y = box["x"] / layout.canvas.width, box["y"] / layout.canvas.height
            w, h = box["width"] / layout.canvas.width, box["height"] / layout.canvas.height
            covered += max(0, min(x + w, subject.x + subject.width) - max(x, subject.x)) * max(0, min(y + h, subject.y + subject.height) - max(y, subject.y))
        overlaps.append(min(1.0, covered / (subject.width * subject.height)))
    return max(overlaps)
