from collections.abc import Sequence

from app.schemas.evaluation import AttentionPrediction, RuleIssue, ScoreBreakdown, VisionReview
from app.schemas.layout import ElementRole

_SEVERITY_PENALTIES = {"critical": 24.0, "high": 12.0, "medium": 6.0, "low": 2.0}


def aggregate_scores(
    *,
    rule_issues: Sequence[RuleIssue],
    vision: VisionReview,
    attention: AttentionPrediction,
    expected_attention_path: Sequence[ElementRole],
) -> ScoreBreakdown:
    hard_rules = max(0.0, 40.0 - sum(_SEVERITY_PENALTIES[issue.severity] for issue in rule_issues))
    vision_score = _vision_score(vision)
    attention_score = _attention_score(attention, expected_attention_path)
    earned = hard_rules + (vision_score or 0) + (attention_score or 0)
    available_weight = 40.0
    if vision_score is not None:
        available_weight += 35.0
    if attention_score is not None:
        available_weight += 25.0
    total = round(earned / available_weight * 100, 2) if available_weight else 0.0
    return ScoreBreakdown(
        hard_rules=hard_rules,
        vision=vision_score,
        attention=attention_score,
        total=total,
        available_weight=available_weight,
    )


def _vision_score(vision: VisionReview) -> float | None:
    if vision.availability == "unavailable" or vision.score is None:
        return None
    return round(vision.score * 0.35, 2)


def _attention_score(
    attention: AttentionPrediction,
    expected_path: Sequence[ElementRole],
) -> float | None:
    if attention.availability == "unavailable":
        return None
    if not expected_path:
        return 25.0
    overlap = sum(
        1
        for expected, actual in zip(expected_path, attention.predicted_path, strict=False)
        if expected == actual
    )
    return round(25.0 * overlap / len(expected_path), 2)
