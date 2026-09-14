import pytest

from app.poster.action_validator import ActionValidationError, validate_actions
from app.poster.template_loader import TemplateLoader
from app.schemas.brief import PosterBrief
from app.schemas.optimization import OptimizationAction


def make_layout():
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


def action(name: str, target_id: str, parameters: dict[str, object]) -> OptimizationAction:
    return OptimizationAction(
        action=name,
        target_id=target_id,
        parameters=parameters,
        reason="测试优化动作",
    )


def test_validator_accepts_safe_title_font_size_change() -> None:
    validate_actions([action("set_font_size", "title", {"font_size": 96})], make_layout())


def test_validator_rejects_unknown_target() -> None:
    with pytest.raises(ActionValidationError, match="Unknown layout element"):
        validate_actions([action("set_font_size", "missing", {"font_size": 96})], make_layout())


def test_validator_rejects_font_size_outside_safe_range() -> None:
    with pytest.raises(ActionValidationError, match="font_size"):
        validate_actions([action("set_font_size", "title", {"font_size": 500})], make_layout())


def test_validator_rejects_brightness_change_for_text_element() -> None:
    with pytest.raises(ActionValidationError, match="main_visual"):
        validate_actions([action("set_brightness", "title", {"brightness": 0.8})], make_layout())


@pytest.mark.parametrize(
    ("name", "parameters"),
    [
        ("set_position", {"x": 0.1, "y": 0.1}),
        ("set_size", {"width": 0.8, "height": 0.8}),
    ],
)
def test_validator_keeps_main_visual_full_bleed(
    name: str,
    parameters: dict[str, object],
) -> None:
    with pytest.raises(ActionValidationError, match="full-bleed"):
        validate_actions([action(name, "main_visual", parameters)], make_layout())
