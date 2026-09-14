"""Evaluate explicit human objectives separately from an overall aesthetic score."""

from app.poster.design_guards import DesignConstraintError, assert_design_constraints
from app.schemas.design_control import (
    BackgroundTreatment, DesignControls, GoalVerification, PosterAnalysis, VerificationCheck,
)
from app.schemas.layout import PosterLayout
from app.schemas.evaluation import AttentionPrediction


def verify_design_goals(
    *, before_layout: PosterLayout, after_layout: PosterLayout,
    before_analysis: PosterAnalysis, after_analysis: PosterAnalysis,
    controls: DesignControls, before_treatment: BackgroundTreatment,
    after_treatment: BackgroundTreatment,
    attention: AttentionPrediction | None = None,
    rejection_reason: str | None = None,
) -> GoalVerification:
    checks: list[VerificationCheck] = []
    if rejection_reason:
        checks.append(VerificationCheck(key="render_guard", label="渲染保护", status="failed", detail=f"本轮尝试违反保留条件，已恢复到本轮开始的海报：{rejection_reason}"))
    try:
        assert_design_constraints(before_layout, after_layout, controls,
                                  before_treatment=before_treatment, after_treatment=after_treatment)
        checks.append(VerificationCheck(key="invariants", label="文字事实与锁定参数", status="passed", detail="元素、文字事实、主视觉构图与明确锁定的参数保持不变。"))
    except DesignConstraintError as error:
        checks.append(VerificationCheck(key="invariants", label="文字事实与锁定参数", status="failed", detail=str(error)))
    old_facts = {fact.element_id: fact for fact in before_analysis.text_facts}
    new_facts = {fact.element_id: fact for fact in after_analysis.text_facts}
    for lock in controls.locks:
        if "typography" not in lock.properties:
            continue
        old, new = old_facts.get(lock.element_id), new_facts.get(lock.element_id)
        if old is None or new is None:
            # Main visual isn't a text element, so this property has no text rendering.
            continue
        same = old.actual_font_size == new.actual_font_size and old.font_name == new.font_name
        checks.append(VerificationCheck(key=f"render_lock:{lock.element_id}", label=f"{lock.element_id} 实际字体锁定", status="passed" if same else "failed", detail="对比实际字体与实际字号，包含自动适配造成的变化。"))
    overflow = [fact.element_id for fact in after_analysis.text_facts if not fact.fits_box]
    checks.append(VerificationCheck(key="text_fit", label="文字区域检查", status="failed" if overflow else "passed" if new_facts else "unavailable", detail=f"超出区域：{', '.join(overflow)}" if overflow else "实际渲染包围框与分配区域比较。"))
    old_values = {feature.key: feature.value for feature in before_analysis.features}
    new_values = {feature.key: feature.value for feature in after_analysis.features}
    for goal in controls.adjustments:
        old, new = old_values.get(goal.trait), new_values.get(goal.trait)
        if old is None or new is None:
            status, detail = "unavailable", "缺少可比较测量，不能宣称目标已达成。"
        elif goal.direction == "preserve":
            tolerance = max(0.005, abs(old) * 0.01)
            status = "passed" if abs(new - old) <= tolerance else "failed"
            detail = f"保留检查允许测量误差 {tolerance:.4f}；不以整体评分代替该条件。"
        else:
            threshold = max(0.005, abs(old) * goal.strength * 0.25)
            delta = new - old if goal.direction == "strengthen" else old - new
            status = "passed" if delta >= threshold else "failed"
            detail = f"本轮要求{'增强' if goal.direction == 'strengthen' else '减弱'}；定向变化至少 {threshold:.4f}。常量背景或自动缩字可能导致目标未达成。"
        checks.append(VerificationCheck(key=goal.trait, label=goal.trait, status=status, detail=detail, before=old, after=new))
    if controls.attention_priority:
        available = attention is not None and attention.availability != "unavailable" and bool(attention.predicted_path)
        matched = available and attention.predicted_path[:len(controls.attention_priority)] == controls.attention_priority
        checks.append(VerificationCheck(key="attention_priority", label="信息注意力优先级", status="passed" if matched else "failed" if available else "unavailable", detail=f"当前预测角色序列：{attention.predicted_path if available else '不可用'}；与用户优先级比较，仅是模型预测代理，不证明真实阅读顺序。"))
    checks.extend(after_analysis.readability_checks)
    if any(check.status == "failed" for check in checks):
        outcome, summary = "not_met", "部分要求未满足，请查看逐项原因，不以总分上涨代替目标达成。"
    elif any(check.status == "unavailable" for check in checks):
        outcome, summary = "unverified", "部分要求缺少验证信号，不能确认全部达成。"
    elif controls.has_request:
        outcome, summary = "met", "已通过当前可测目标及保护条件检查；不代表审美或真实注意力得到证明。"
    else:
        outcome, summary = "no_change_requested", "本轮未指定结构化目标，已检查基础保护条件。"
    return GoalVerification(checks=checks, outcome=outcome, summary=summary)
