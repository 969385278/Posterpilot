from app.evaluation.hard_rules import evaluate_hard_rules
from app.poster.template_loader import TemplateLoader
from app.schemas.brief import PosterBrief
from app.schemas.layout import NormalizedBox


def _layout():
    brief = PosterBrief.model_validate(
        {
            "poster_type": "cultural_event",
            "topic": "红楼梦研讨分享会",
            "target_audience": "大学生",
            "title": "红楼梦研讨分享会",
            "event_time": "2026年7月20日 19:00",
            "location": "图书馆报告厅",
            "organizer": "文学社",
        }
    )
    return TemplateLoader("data/templates").instantiate("cultural_event", brief)


def test_default_template_has_no_overlap_or_hierarchy_issue() -> None:
    issues = evaluate_hard_rules(_layout())

    assert not {issue.rule_id for issue in issues} & {"elements_overlap", "title_hierarchy"}


def test_evaluator_reports_overlapping_content_and_weak_title_hierarchy() -> None:
    layout = _layout()
    title = next(element for element in layout.elements if element.role == "title")
    event_info = next(element for element in layout.elements if element.role == "event_info")
    title.box = NormalizedBox(x=0.08, y=0.79, width=0.84, height=0.10)
    title.font_size = event_info.font_size

    issues = evaluate_hard_rules(layout)

    issue_ids = {issue.rule_id for issue in issues}
    assert "elements_overlap" in issue_ids
    assert "title_hierarchy" in issue_ids


def test_evaluator_reports_too_many_text_colors() -> None:
    layout = _layout()
    for index, element in enumerate(layout.elements):
        element.color = f"#{index + 1:06X}"

    issues = evaluate_hard_rules(layout)

    assert any(issue.rule_id == "too_many_colors" for issue in issues)
