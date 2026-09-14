import pytest
from pydantic import ValidationError

from app.schemas.design_spec import DesignSpec


def valid_design_spec_data() -> dict[str, object]:
    return {
        "design_goal": "面向大学生的文学研讨活动海报",
        "template_id": "cultural_event",
        "expected_attention_path": ["title", "main_visual", "event_info"],
        "layout": {
            "canvas": {"width": 1080, "height": 1440},
            "elements": [
                {
                    "id": "title",
                    "role": "title",
                    "content": "红楼梦研讨分享会",
                    "box": {"x": 0.08, "y": 0.06, "width": 0.84, "height": 0.17},
                    "font_size": 82,
                    "font_family": "Source Han Serif SC",
                    "color": "#7A2330",
                    "alignment": "left",
                },
                {
                    "id": "main_visual",
                    "role": "main_visual",
                    "box": {"x": 0.08, "y": 0.25, "width": 0.84, "height": 0.45},
                },
                {
                    "id": "event_info",
                    "role": "event_info",
                    "content": "2026年7月20日 19:00｜图书馆报告厅",
                    "box": {"x": 0.08, "y": 0.76, "width": 0.84, "height": 0.17},
                    "font_size": 34,
                    "font_family": "Source Han Sans SC",
                    "color": "#26221E",
                    "alignment": "left",
                },
            ],
        },
        "palette": {
            "background": "#E8DDC7",
            "primary": "#7A2330",
            "secondary": "#26221E",
        },
        "visual_prompt": "古典园林意象，现代编辑设计，无文字",
        "negative_prompt": "text, watermark, logo",
        "knowledge_refs": ["rule-layout-title-focus-001"],
    }


def test_design_spec_accepts_normalized_layout() -> None:
    spec = DesignSpec.model_validate(valid_design_spec_data())

    assert spec.layout.elements[0].box.x == 0.08
    assert spec.expected_attention_path[0] == "title"


def test_design_spec_rejects_invalid_hex_color() -> None:
    data = valid_design_spec_data()
    data["palette"] = {
        "background": "cream",
        "primary": "#7A2330",
        "secondary": "#26221E",
    }

    with pytest.raises(ValidationError):
        DesignSpec.model_validate(data)


def test_design_spec_rejects_box_extending_past_canvas() -> None:
    data = valid_design_spec_data()
    layout = data["layout"]
    assert isinstance(layout, dict)
    elements = layout["elements"]
    assert isinstance(elements, list)
    first = elements[0]
    assert isinstance(first, dict)
    first["box"] = {"x": 0.8, "y": 0.1, "width": 0.4, "height": 0.2}

    with pytest.raises(ValidationError, match="canvas bounds"):
        DesignSpec.model_validate(data)

