from pathlib import Path

import pytest

from app.poster.template_loader import TemplateLoader, UnknownTemplateError
from app.schemas.brief import PosterBrief


def make_brief() -> PosterBrief:
    return PosterBrief.model_validate(
        {
            "poster_type": "cultural_event",
            "topic": "红楼梦研讨分享会",
            "target_audience": "大学生",
            "title": "红楼梦研讨分享会",
            "subtitle": "从人物关系看古典文学",
            "event_time": "2026年7月20日 19:00",
            "location": "图书馆报告厅",
            "organizer": "文学社",
        }
    )


def test_loader_lists_three_supported_templates() -> None:
    loader = TemplateLoader(Path("data/templates"))

    assert loader.list_template_ids() == ["campus_lecture", "club_recruitment", "cultural_event"]


def test_loader_instantiates_cultural_event_with_brief_content() -> None:
    loader = TemplateLoader(Path("data/templates"))

    layout = loader.instantiate("cultural_event", make_brief())

    elements = {element.id: element for element in layout.elements}
    assert layout.canvas.width == 1080
    assert elements["title"].content == "红楼梦研讨分享会"
    assert elements["subtitle"].content == "从人物关系看古典文学"
    assert "2026年7月20日" in elements["event_info"].content
    assert elements["main_visual"].box.model_dump() == {
        "x": 0.0,
        "y": 0.0,
        "width": 1.0,
        "height": 1.0,
    }


def test_loader_rejects_unknown_template() -> None:
    loader = TemplateLoader(Path("data/templates"))

    with pytest.raises(UnknownTemplateError, match="Unknown poster template"):
        loader.instantiate("unknown", make_brief())


@pytest.mark.parametrize("template", ["cultural_event", "campus_lecture", "club_recruitment"])
@pytest.mark.parametrize("details, expected", [({}, None), ({"event_time": "18:30"}, "18:30"), ({"location": "图书馆"}, "图书馆")])
def test_optional_information_is_omitted_without_placeholders(template, details, expected):
    from app.evaluation.hard_rules import evaluate_hard_rules
    brief = PosterBrief(title="摄影社招新", poster_type=template, **details)
    layout = TemplateLoader().instantiate(template, brief)
    elements = {element.role: element for element in layout.elements}
    assert "organizer" not in elements and "subtitle" not in elements
    if expected is None:
        assert set(elements) == {"title", "main_visual"}
    else:
        assert elements["event_info"].content == expected
    assert not any(issue.rule_id == "required_information_missing" for issue in evaluate_hard_rules(layout))
