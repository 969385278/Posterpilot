import base64
import io
from pathlib import Path

from PIL import Image

from app.agent.nodes.generate_visual import generate_visual
from app.agent.nodes.render_draft import render_draft
from app.agent.state import initial_agent_state
from app.agent.tools.generation_tools import materialize_generated_image
from app.poster.renderer import PosterRenderer
from app.providers.image.base import GeneratedImage
from app.schemas.brief import PosterBrief
from app.schemas.design_spec import DesignSpec


class FakeImageProvider:
    async def generate(
        self,
        prompt: str,
        *,
        size: str | None = None,
        reference_image_url: str = "",
    ):
        assert "no text" in prompt
        return GeneratedImage(image_url=_image_data_url(), provider="fake", model="fake-v1")


def _image_data_url() -> str:
    image = Image.new("RGB", (320, 480), "#CBAA84")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"


def _state():
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
    state = initial_agent_state(brief)
    state["design_spec"] = DesignSpec.model_validate(
        {
            "design_goal": "突出活动主题和时间地点",
            "template_id": "cultural_event",
            "expected_attention_path": ["title", "main_visual", "event_info"],
            "layout": {
                "canvas": {"width": 1080, "height": 1440},
                "elements": [
                    {
                        "id": "title",
                        "role": "title",
                        "content": "红楼梦研讨分享会",
                        "box": {"x": 0.08, "y": 0.07, "width": 0.84, "height": 0.15},
                        "font_size": 88,
                    },
                    {
                        "id": "visual",
                        "role": "main_visual",
                        "box": {"x": 0.08, "y": 0.31, "width": 0.84, "height": 0.43},
                    },
                    {
                        "id": "event-info",
                        "role": "event_info",
                        "content": "2026年7月20日 19:00\\n图书馆报告厅",
                        "box": {"x": 0.08, "y": 0.79, "width": 0.84, "height": 0.1},
                        "font_size": 32,
                    },
                ],
            },
            "palette": {"background": "#E8DDC7", "primary": "#7A2330", "secondary": "#4A4038"},
            "visual_prompt": "classical Chinese literature mood, no text",
        }
    )
    return state


async def test_generation_and_rendering_nodes_create_initial_artifacts(tmp_path: Path) -> None:
    state = _state()
    generated = await generate_visual(
        state,
        image_provider=FakeImageProvider(),
        run_directory=tmp_path,
    )
    rendered = render_draft(
        {**state, **generated},
        renderer=PosterRenderer(),
        run_directory=tmp_path,
    )

    assert Path(generated["main_visual_path"]).is_file()
    assert Path(rendered["poster_initial_path"]).is_file()
    assert [event["node"] for event in rendered["events"]] == [
        "generate_visual",
        "render_draft",
    ]


async def test_materialize_generated_image_rejects_unknown_url_scheme(tmp_path: Path) -> None:
    image = GeneratedImage(image_url="ftp://example.test/poster.png", provider="fake", model="fake")

    try:
        await materialize_generated_image(image, output_path=tmp_path / "poster.png")
    except ValueError as error:
        assert "unsupported" in str(error).lower()
    else:
        raise AssertionError("Expected unsupported image URL to fail")
