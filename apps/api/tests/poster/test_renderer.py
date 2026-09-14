from pathlib import Path

from PIL import Image, ImageChops, ImageOps

from app.poster.renderer import PosterRenderer
from app.poster.template_loader import TemplateLoader
from app.schemas.brief import PosterBrief


def make_layout():
    brief = PosterBrief.model_validate(
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
    return TemplateLoader("data/templates").instantiate("cultural_event", brief)


def test_renderer_outputs_vertical_png_and_element_bounds(tmp_path: Path) -> None:
    output_path = tmp_path / "poster.png"
    main_visual_path = tmp_path / "main-visual.png"
    Image.new("RGB", (640, 480), "#8B1E2D").save(main_visual_path)
    renderer = PosterRenderer()

    result = renderer.render(
        make_layout(),
        main_visual_path=main_visual_path,
        output_path=output_path,
        background_color="#E8DDC7",
    )

    with Image.open(output_path) as image:
        assert image.size == (1080, 1440)
    bounds = {element.id: element for element in result.elements}
    assert bounds["title"].actual_box.width > 0
    assert bounds["main_visual"].actual_box == type(bounds["main_visual"].actual_box)(
        x=0,
        y=0,
        width=1080,
        height=1440,
    )
    assert result.path == output_path


def test_renderer_places_text_over_a_full_bleed_visual(tmp_path: Path) -> None:
    output_path = tmp_path / "poster.png"
    main_visual_path = tmp_path / "main-visual.png"
    visual = Image.new("RGB", (300, 400), "#58718A")
    visual.save(main_visual_path)

    result = PosterRenderer().render(
        make_layout(),
        main_visual_path=main_visual_path,
        output_path=output_path,
        background_color="#E8DDC7",
    )

    expected_background = ImageOps.fit(visual, (1080, 1440))
    title_box = next(item.actual_box for item in result.elements if item.id == "title")
    title_region = (
        title_box.x,
        title_box.y,
        title_box.x + title_box.width,
        title_box.y + title_box.height,
    )
    with Image.open(output_path) as rendered:
        assert rendered.getpixel((540, 720)) == expected_background.getpixel((540, 720))
        assert ImageChops.difference(
            rendered.crop(title_region),
            expected_background.crop(title_region),
        ).getbbox() is not None


def test_renderer_rejects_missing_main_visual(tmp_path: Path) -> None:
    renderer = PosterRenderer()

    try:
        renderer.render(
            make_layout(),
            main_visual_path=tmp_path / "missing.png",
            output_path=tmp_path / "poster.png",
            background_color="#E8DDC7",
        )
    except FileNotFoundError as error:
        assert "main visual" in str(error).lower()
    else:
        raise AssertionError("Expected missing main visual to raise FileNotFoundError")
