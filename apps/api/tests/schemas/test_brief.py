import pytest
from pydantic import ValidationError

from app.schemas.brief import CanvasSize, PosterBrief


def valid_brief_data() -> dict[str, object]:
    return {
        "poster_type": "cultural_event",
        "topic": "红楼梦研讨分享会",
        "target_audience": "大学生",
        "title": "红楼梦研讨分享会",
        "subtitle": "从人物关系看古典文学",
        "event_time": "2026年7月20日 19:00",
        "location": "图书馆报告厅",
        "organizer": "文学社",
        "style_preferences": ["东方", "典雅", "现代"],
        "color_preferences": ["米白", "暗红"],
        "canvas": {"width": 1080, "height": 1440},
    }


def test_brief_accepts_complete_vertical_activity_poster() -> None:
    brief = PosterBrief.model_validate(valid_brief_data())

    assert brief.poster_type == "cultural_event"
    assert brief.canvas == CanvasSize(width=1080, height=1440)
    assert brief.style_preferences == ["东方", "典雅", "现代"]


@pytest.mark.parametrize("field", ["title"])
def test_brief_rejects_missing_required_event_information(field: str) -> None:
    data = valid_brief_data()
    data.pop(field)

    with pytest.raises(ValidationError):
        PosterBrief.model_validate(data)


def test_brief_rejects_non_vertical_canvas() -> None:
    data = valid_brief_data()
    data["canvas"] = {"width": 1440, "height": 1080}

    with pytest.raises(ValidationError, match="vertical"):
        PosterBrief.model_validate(data)


def test_only_title_is_required_and_topic_defaults_to_title():
    brief = PosterBrief(title="  摄影社招新  ")
    assert brief.title == brief.topic == "摄影社招新"
    assert brief.event_time == brief.location == brief.organizer == brief.target_audience == ""
    assert brief.subtitle is None


def test_optional_blanks_and_nulls_do_not_create_facts_or_attention_roles():
    brief = PosterBrief(title="海报", topic="  ", subtitle="  ", event_time=None,
                        location="  ", organizer=None, target_audience=None,
                        attention_priority=["event_info", "organizer", "subtitle", "title"])
    assert brief.topic == "海报"
    assert brief.subtitle is None
    assert brief.attention_priority == ["title"]


@pytest.mark.parametrize("title", ["", "   "])
def test_blank_title_is_rejected(title):
    with pytest.raises(ValidationError):
        PosterBrief(title=title)
