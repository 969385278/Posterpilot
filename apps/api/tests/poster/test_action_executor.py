from app.poster.action_executor import apply_optimization_actions
from app.poster.template_loader import TemplateLoader
from app.schemas.brief import PosterBrief
from app.schemas.optimization import OptimizationAction


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


def test_executor_applies_safe_layout_actions_without_mutating_original() -> None:
    layout = _layout()
    updated = apply_optimization_actions(
        layout,
        [
            OptimizationAction(
                action="set_font_size",
                target_id="title",
                parameters={"font_size": 96},
                reason="强化标题",
            ),
            OptimizationAction(
                action="set_color",
                target_id="title",
                parameters={"color": "#8A1F2D"},
                reason="提升对比",
            ),
        ],
    )

    assert next(element for element in layout.elements if element.id == "title").font_size == 88
    title = next(element for element in updated.elements if element.id == "title")
    assert title.font_size == 96
    assert title.color == "#8A1F2D"


def test_executor_rejects_action_that_pushes_element_outside_canvas() -> None:
    layout = _layout()
    action = OptimizationAction(
        action="set_position",
        target_id="title",
        parameters={"x": 0.9, "y": 0.07},
        reason="错误操作",
    )

    try:
        apply_optimization_actions(layout, [action])
    except ValueError as error:
        assert "canvas" in str(error).lower()
    else:
        raise AssertionError("Expected canvas overflow to be rejected")
