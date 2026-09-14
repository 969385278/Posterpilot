"""Server-side invariants shared by ReAct tools and candidate layout selection."""

from app.schemas.design_control import BackgroundTreatment, DesignControls
from app.schemas.layout import PosterLayout


class DesignConstraintError(ValueError):
    pass


_TYPOGRAPHY_FIELDS = ("font_size", "font_family", "color", "alignment", "line_spacing", "opacity")


def validate_control_targets(controls: DesignControls, layout: PosterLayout) -> None:
    elements = {element.id: element for element in layout.elements}
    unknown = {lock.element_id for lock in controls.locks} - elements.keys()
    if unknown:
        raise DesignConstraintError(f"未知锁定元素：{', '.join(sorted(unknown))}")
    unknown_roles = set(controls.attention_priority) - {element.role for element in layout.elements}
    if unknown_roles:
        raise DesignConstraintError(f"当前海报没有这些优先级元素：{', '.join(sorted(unknown_roles))}")


def assert_design_constraints(
    before: PosterLayout,
    after: PosterLayout,
    controls: DesignControls,
    *,
    before_treatment: BackgroundTreatment | None = None,
    after_treatment: BackgroundTreatment | None = None,
) -> None:
    validate_control_targets(controls, before)
    original = {element.id: element for element in before.elements}
    updated = {element.id: element for element in after.elements}
    if original.keys() != updated.keys() or before.canvas != after.canvas:
        raise DesignConstraintError("本轮不允许增删元素或改变画布尺寸")
    if [element.id for element in before.elements] != [element.id for element in after.elements]:
        raise DesignConstraintError("本轮不允许改变图层绘制顺序")
    for key, element in original.items():
        candidate = updated[key]
        if element.role != candidate.role or element.content != candidate.content:
            raise DesignConstraintError(f"必须保留元素 {key} 的角色和文字事实")
        if element.role == "main_visual" and element != candidate:
            raise DesignConstraintError("主视觉构图固定，只能通过专用工具处理背景色彩")
    for lock in controls.locks:
        old, new = original[lock.element_id], updated[lock.element_id]
        for field in lock.properties:
            changed = (
                old.box != new.box if field == "position" else
                any(getattr(old, name) != getattr(new, name) for name in _TYPOGRAPHY_FIELDS)
                if field == "typography" else old.content != new.content
            )
            if changed:
                raise DesignConstraintError(f"元素 {lock.element_id} 的 {field} 已锁定")
    for adjustment in controls.adjustments:
        if adjustment.direction != "preserve":
            continue
        if adjustment.trait == "title_emphasis":
            # Emphasis is relative: changing other text sizes also changes it.
            if any(old.font_size != updated[key].font_size for key, old in original.items() if old.content):
                raise DesignConstraintError("保留标题强调程度时，不允许改变文字字号比例")
        elif before_treatment is not None and after_treatment is not None:
            field = "contrast" if adjustment.trait == "background_contrast" else "saturation"
            if getattr(before_treatment, field) != getattr(after_treatment, field):
                raise DesignConstraintError(f"{adjustment.trait} 已设为保留")


def assert_rendered_locks(before_analysis, after_analysis, controls: DesignControls) -> None:
    original = {fact.element_id: fact for fact in before_analysis.text_facts}
    updated = {fact.element_id: fact for fact in after_analysis.text_facts}
    for lock in controls.locks:
        if "typography" not in lock.properties or lock.element_id not in original:
            continue
        old, new = original[lock.element_id], updated.get(lock.element_id)
        if new is None or (old.actual_font_size, old.font_name) != (new.actual_font_size, new.font_name):
            raise DesignConstraintError(f"元素 {lock.element_id} 的实际字体/字号已锁定，不能因自动适配而变化")
    old_values = {feature.key: feature.value for feature in before_analysis.features}
    new_values = {feature.key: feature.value for feature in after_analysis.features}
    for goal in controls.adjustments:
        if goal.direction != "preserve":
            continue
        old, new = old_values.get(goal.trait), new_values.get(goal.trait)
        if old is None or new is None:
            raise DesignConstraintError(f"无法验证 {goal.trait} 的保留条件")
        if abs(new - old) > max(0.005, abs(old) * 0.01):
            raise DesignConstraintError(f"{goal.trait} 的实测值违反保留条件")
