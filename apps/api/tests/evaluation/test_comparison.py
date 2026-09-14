import pytest

from app.evaluation.comparison import compare_reports
from app.evaluation.report_builder import build_report
from app.evaluation.score_aggregator import aggregate_scores
from app.schemas.evaluation import AttentionPrediction, VisionReview


def make_report(vision_score=60):
    vision = VisionReview(
        availability="unavailable" if vision_score is None else "available",
        score=vision_score,
    )
    attention = AttentionPrediction(availability="unavailable")
    scores = aggregate_scores(rule_issues=[], vision=vision, attention=attention, expected_attention_path=[])
    return build_report([], attention, vision, scores)


def test_service_failure_is_not_a_quality_improvement():
    before, after = make_report(), make_report(None)
    assert after.scores.total > before.scores.total
    result = compare_reports(before, after)
    assert result.delta is None
    assert result.outcome == "not_comparable"
    assert "信号" in result.reason


def test_zero_is_a_valid_signal_and_not_missing():
    assert compare_reports(make_report(0), make_report(10)).outcome == "improved"
    assert compare_reports(make_report(0), make_report(None)).delta is None


def test_rule_version_change_prevents_comparison():
    before, after = make_report(), make_report()
    before.evaluator_version = "evaluation-v1"
    result = compare_reports(before, after)
    assert result.delta is None
    assert "版本" in result.reason


def test_new_human_goal_is_not_reported_as_a_score_improvement():
    before, after = make_report(60), make_report(90)
    after.design_goal_context = {"attention_priority": ["event_info", "title"]}
    comparison = compare_reports(before, after)
    assert comparison.delta is None
    assert "目标" in comparison.reason


@pytest.mark.parametrize("score, outcome", [(50, "declined"), (60, "unchanged"), (70, "improved")])
def test_matching_reports_can_be_compared(score, outcome):
    assert compare_reports(make_report(60), make_report(score)).outcome == outcome


def test_finalize_and_round_snapshot_preserve_not_comparable():
    from app.agent.nodes.complete_round import complete_round
    from app.agent.nodes.finalize import finalize
    from tests.agent.test_rendering_nodes import _state

    state = {
        **_state(), "evaluation_initial": make_report(),
        "evaluation_optimized": make_report(None),
        "poster_initial_path": "poster_initial.png",
        "poster_optimized_path": "poster_round_1.png", "round_number": 1,
        "round_snapshots": [], "tool_traces": [],
    }
    snapshot = complete_round(state)["round_snapshots"][0]
    assert snapshot.score_delta is None
    assert snapshot.comparison_reason
    result = finalize({**state, "round_snapshots": [snapshot]})["result"]
    assert result["outcome"] == "not_comparable"
    assert result["score_delta"] is None
