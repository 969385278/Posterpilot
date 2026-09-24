"""Verify exact element requests against layout and actual rendered text metadata."""

from app.schemas.design_control import VerificationCheck


def element_goal_checks(controls, before_layout, after_layout, before_analysis, after_analysis):
    old = {item.id: item for item in before_layout.elements}
    new = {item.id: item for item in after_layout.elements}
    facts = {item.element_id: item for item in after_analysis.text_facts}
    checks = []
    for goal in controls.element_goals:
        target = new.get(goal.element_id)
        prior = old.get(goal.element_id)
        actual = previous = None
        status = "unavailable"
        if goal.kind == "opacity":
            detail = f"要求不透明度 {goal.opacity:g}；核对布局参数与实际渲染元数据。"
            fact = facts.get(goal.element_id)
            if target is not None and fact is not None:
                actual = fact.opacity
                previous = prior.opacity if prior else None
                status = (
                    "passed"
                    if (
                        abs(actual - goal.opacity) <= 1e-6
                        and abs(target.opacity - goal.opacity) <= 1e-6
                    )
                    else "failed"
                )
        else:
            detail = f"要求文字框 {goal.edge} 对齐 {goal.reference_id}；不是字形边缘对齐。"
            reference = new.get(goal.reference_id)
            if (
                target is not None
                and reference is not None
                and all(key in facts for key in [goal.element_id, goal.reference_id])
            ):
                factor = {"left": 0, "center": 0.5, "right": 1}[goal.edge]
                actual = abs(
                    (target.box.x + target.box.width * factor)
                    - (reference.box.x + reference.box.width * factor)
                )
                old_ref = old.get(goal.reference_id)
                if prior and old_ref:
                    previous = abs(
                        (prior.box.x + prior.box.width * factor)
                        - (old_ref.box.x + old_ref.box.width * factor)
                    )
                status = "passed" if actual <= 1e-6 else "failed"
        checks.append(
            VerificationCheck(
                key=f"element:{goal.kind}:{goal.element_id}",
                label=f"{goal.element_id} {'不透明度' if goal.kind == 'opacity' else '文字框对齐'}",
                status=status,
                detail=detail,
                before=previous,
                after=actual,
            )
        )
    return checks
