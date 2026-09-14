from dataclasses import dataclass

from app.schemas.evaluation import EvaluationReport


@dataclass(frozen=True)
class ScoreComparison:
    delta: float | None
    outcome: str
    reason: str | None = None


def compare_reports(before: EvaluationReport, after: EvaluationReport) -> ScoreComparison:
    """Compare only like-for-like reports; missing signals are not zero scores."""
    if before.evaluator_version != after.evaluator_version:
        return ScoreComparison(None, "not_comparable", "评测规则版本不同，不能直接比较总分。")
    if before.design_goal_context != after.design_goal_context:
        return ScoreComparison(None, "not_comparable", "用户设计目标或信息优先级改变，不能把跨目标分差当作优化提升。")
    for signal in ("vision", "attention"):
        if (getattr(before.scores, signal) is None) != (getattr(after.scores, signal) is None):
            return ScoreComparison(None, "not_comparable", "两次评测的可用信号不同，不能直接比较总分。")
    if before.scores.available_weight != after.scores.available_weight:
        return ScoreComparison(None, "not_comparable", "两次评测权重不同，不能直接比较总分。")
    if before.scores.attention is not None and before.attention.model != after.attention.model:
        return ScoreComparison(None, "not_comparable", "注意力模型不同，不能直接比较总分。")
    delta = round(after.scores.total - before.scores.total, 2)
    return ScoreComparison(delta, "improved" if delta > 0 else "declined" if delta < 0 else "unchanged")
