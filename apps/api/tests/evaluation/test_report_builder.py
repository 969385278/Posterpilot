from app.evaluation.report_builder import build_report
from app.evaluation.score_aggregator import aggregate_scores
from app.schemas.evaluation import AttentionPrediction, RuleIssue, VisionReview


def test_report_prioritizes_critical_rule_and_vision_issue() -> None:
    rules = [
        RuleIssue(
            rule_id="overflow",
            problem="标题出界",
            severity="critical",
            evidence="x=1.02",
        )
    ]
    vision = VisionReview(
        availability="available",
        score=70,
        summary="需要优化",
        issues=[{"problem": "对比不足", "reason": "文字不清晰", "severity": "high"}],
    )
    attention = AttentionPrediction(availability="unavailable", error="offline")
    scores = aggregate_scores(
        rule_issues=rules,
        vision=vision,
        attention=attention,
        expected_attention_path=["title"],
    )

    report = build_report(rules, attention, vision, scores)

    assert report.primary_issues == ["标题出界", "对比不足"]
    assert report.evaluator_version == "evaluation-v2-aoi-paint-order"
