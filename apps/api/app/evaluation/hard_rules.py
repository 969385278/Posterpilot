from app.schemas.evaluation import RuleIssue
from app.schemas.layout import LayoutElement, PosterLayout
from app.schemas.design_control import DesignControls

_TEXT_ROLES = {"title", "subtitle", "event_info", "organizer"}
_REQUIRED_ROLES = {"title", "main_visual"}


def evaluate_hard_rules(layout: PosterLayout, controls: DesignControls | None = None) -> list[RuleIssue]:
    """Evaluate deterministic poster rules before model-based evaluation."""
    issues: list[RuleIssue] = []
    issues.extend(_required_content_issues(layout))
    issues.extend(_overlap_issues(layout))
    issues.extend(_margin_issues(layout))
    soften_title = controls and (
        any(goal.trait == "title_emphasis" and goal.direction in {"weaken", "preserve"} for goal in controls.adjustments)
        or (controls.attention_priority and controls.attention_priority[0] != "title")
    )
    if not soften_title:
        issues.extend(_hierarchy_issues(layout))
    issues.extend(_density_issues(layout))
    issues.extend(_color_issues(layout))
    return issues


def _required_content_issues(layout: PosterLayout) -> list[RuleIssue]:
    roles = {element.role for element in layout.elements}
    missing = sorted(_REQUIRED_ROLES - roles)
    if not missing:
        return []
    return [
        _issue(
            "required_information_missing",
            "缺少海报必要区域",
            "critical",
            f"缺少必要角色：{', '.join(missing)}。",
            missing,
            ["set_position", "set_size"],
        )
    ]


def _overlap_issues(layout: PosterLayout) -> list[RuleIssue]:
    content_elements = [element for element in layout.elements if element.role in _TEXT_ROLES]
    issues: list[RuleIssue] = []
    for index, first in enumerate(content_elements):
        for second in content_elements[index + 1 :]:
            if _intersection_area(first, second) > 0.001:
                issues.append(
                    _issue(
                        "elements_overlap",
                        "文字区域发生重叠",
                        "high",
                        f"{first.id} 与 {second.id} 的布局区域重叠。",
                        [first.id, second.id],
                        ["set_position", "set_size", "set_font_size"],
                    )
                )
    return issues


def _margin_issues(layout: PosterLayout) -> list[RuleIssue]:
    unsafe = [
        element.id
        for element in layout.elements
        if element.role in _TEXT_ROLES and _nearest_edge(element) < 0.03
    ]
    if not unsafe:
        return []
    return [
        _issue(
            "unsafe_margin",
            "文字离画布边缘过近",
            "medium",
            "至少一个文字区域距边缘小于画布的 3%。",
            unsafe,
            ["set_position", "set_size"],
        )
    ]


def _hierarchy_issues(layout: PosterLayout) -> list[RuleIssue]:
    title = next((element for element in layout.elements if element.role == "title"), None)
    others = [
        element
        for element in layout.elements
        if element.role in _TEXT_ROLES and element.role != "title"
    ]
    if title is None or not others:
        return []
    title_size = title.font_size or 32
    highest_other = max(element.font_size or 32 for element in others)
    if title_size >= highest_other * 1.25:
        return []
    return [
        _issue(
            "title_hierarchy",
            "标题层级不足",
            "medium",
            f"标题字号 {title_size} 未达到次级文字最大字号 {highest_other} 的 1.25 倍。",
            [title.id],
            ["set_font_size"],
        )
    ]


def _density_issues(layout: PosterLayout) -> list[RuleIssue]:
    event_info = next(
        (element for element in layout.elements if element.role == "event_info"),
        None,
    )
    if event_info is None or not event_info.content:
        return []
    content_length = len(event_info.content.replace("\n", ""))
    density = content_length / (event_info.box.width * event_info.box.height)
    if density <= 700:
        return []
    return [
        _issue(
            "event_info_density",
            "活动信息区过密",
            "medium",
            f"活动信息文字密度为 {density:.0f} 字符/归一化面积。",
            [event_info.id],
            ["set_size", "set_font_size", "set_line_spacing"],
        )
    ]


def _color_issues(layout: PosterLayout) -> list[RuleIssue]:
    colors = {element.color.lower() for element in layout.elements if element.color}
    if len(colors) <= 3:
        return []
    return [
        _issue(
            "too_many_colors",
            "主要文字颜色过多",
            "low",
            f"当前布局使用了 {len(colors)} 种元素颜色，建议控制在 3 种以内。",
            [element.id for element in layout.elements if element.color],
            ["set_color"],
        )
    ]


def _intersection_area(first: LayoutElement, second: LayoutElement) -> float:
    left = max(first.box.x, second.box.x)
    top = max(first.box.y, second.box.y)
    right = min(first.box.x + first.box.width, second.box.x + second.box.width)
    bottom = min(first.box.y + first.box.height, second.box.y + second.box.height)
    return max(0.0, right - left) * max(0.0, bottom - top)


def _nearest_edge(element: LayoutElement) -> float:
    return min(
        element.box.x,
        element.box.y,
        1 - element.box.x - element.box.width,
        1 - element.box.y - element.box.height,
    )


def _issue(
    rule_id: str,
    problem: str,
    severity: str,
    evidence: str,
    affected_elements: list[str],
    actions: list[str],
) -> RuleIssue:
    return RuleIssue(
        rule_id=rule_id,
        problem=problem,
        severity=severity,  # type: ignore[arg-type]
        evidence=evidence,
        affected_elements=affected_elements,
        suggested_action_types=actions,
    )
