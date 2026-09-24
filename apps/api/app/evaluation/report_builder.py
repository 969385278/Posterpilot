from collections.abc import Sequence

from app.schemas.evaluation import (
    AttentionPrediction,
    EvaluationReport,
    RuleIssue,
    ScoreBreakdown,
    VisionReview,
)

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def build_report(
    rule_issues: Sequence[RuleIssue],
    attention: AttentionPrediction,
    vision: VisionReview,
    scores: ScoreBreakdown,
) -> EvaluationReport:
    sorted_rules = sorted(rule_issues, key=lambda item: _SEVERITY_ORDER[item.severity])
    primary = [issue.problem for issue in sorted_rules]
    primary.extend(
        issue.problem
        for issue in sorted(vision.issues, key=lambda item: _SEVERITY_ORDER[item.severity])
    )
    return EvaluationReport(
        rule_issues=list(rule_issues),
        attention=attention,
        vision=vision,
        scores=scores,
        primary_issues=primary[:5],
        evaluator_version="evaluation-v4-element-goals",
    )
