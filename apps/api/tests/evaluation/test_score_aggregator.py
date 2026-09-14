from app.evaluation.score_aggregator import aggregate_scores
from app.schemas.evaluation import AttentionPrediction, RuleIssue, VisionReview


def _issue(severity: str) -> RuleIssue:
    return RuleIssue(
        rule_id="test",
        problem="问题",
        severity=severity,
        evidence="证据",
    )


def test_aggregate_scores_uses_all_three_evaluator_weights() -> None:
    scores = aggregate_scores(
        rule_issues=[_issue("high")],
        vision=VisionReview(availability="available", score=80, summary="可读"),
        attention=AttentionPrediction(
            availability="available",
            predicted_path=["title", "event_info"],
        ),
        expected_attention_path=["title", "event_info"],
    )

    assert scores.hard_rules == 28
    assert scores.vision == 28
    assert scores.attention == 25
    assert scores.total == 81
    assert scores.available_weight == 100


def test_aggregate_scores_keeps_unavailable_components_out_of_total() -> None:
    scores = aggregate_scores(
        rule_issues=[_issue("medium")],
        vision=VisionReview(availability="unavailable", error="missing"),
        attention=AttentionPrediction(availability="unavailable", error="offline"),
        expected_attention_path=["title"],
    )

    assert scores.hard_rules == 34
    assert scores.vision is None
    assert scores.attention is None
    assert scores.total == 85
    assert scores.available_weight == 40
