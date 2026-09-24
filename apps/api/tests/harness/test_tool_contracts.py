"""Release gate contract: actual implementations, guards and pixel rendering."""

import pytest
from PIL import Image, ImageChops

from app.agent.tools.extensions import execute_extension
from app.evaluation.readability import text_readability_checks
from app.poster.design_guards import DesignConstraintError
from app.poster.renderer import PosterRenderer
from app.schemas.design_control import BackgroundTreatment, DesignControls
from app.schemas.layout import NormalizedBox
from tests.poster.test_action_validator import make_layout


def apply(name, arguments, layout=None, controls=None):
    layout = layout or make_layout()
    return execute_extension(
        name, arguments, layout, baseline=layout, controls=controls or DesignControls()
    )[0]


def test_opacity_changes_rendered_pixels_without_changing_facts_or_background(tmp_path):
    layout = make_layout()
    changed = apply("set_text_opacity", {"target_ids": ["title"], "opacity": 0.5}, layout)
    original_by_id = {item.id: item for item in layout.elements}
    for element in changed.elements:
        old = original_by_id[element.id]
        if element.id != "title":
            assert old == element
        assert old.content == element.content and old.box == element.box
    assert original_by_id["title"].opacity == 1
    background = tmp_path / "visual.png"
    Image.new("RGB", (1080, 1440), "#112233").save(background)
    renderer = PosterRenderer()
    rendered = {}
    for name, source in (("before", layout), ("after", changed)):
        rendered[name] = renderer.render(
            source,
            main_visual_path=background,
            output_path=tmp_path / f"{name}.png",
            background_color="#112233",
        )
    with Image.open(tmp_path / "before.png") as before, Image.open(tmp_path / "after.png") as after:
        assert ImageChops.difference(before, after).getbbox() is not None
        assert before.getpixel((540, 720)) == after.getpixel((540, 720))
    measured = {}
    for name, source in (("before", layout), ("after", changed)):
        measured[name] = next(
            check.after
            for check in text_readability_checks(
                source,
                main_visual_path=background,
                treatment=BackgroundTreatment(),
                text_facts=rendered[name].text_facts,
            )
            if check.key == "readability:title"
        )
    assert measured["after"] < measured["before"]


@pytest.mark.parametrize("edge", ["left", "center", "right"])
def test_group_alignment_has_shared_edge_and_preserves_other_dimensions(edge):
    layout = make_layout()
    title = next(item for item in layout.elements if item.id == "title")
    title.box = NormalizedBox(x=0.1, y=0.1, width=0.6, height=0.15)
    target = next(item for item in layout.elements if item.id == "event_info")
    target.box = NormalizedBox(x=0.2, y=0.7, width=0.4, height=0.1)
    changed = apply(
        "align_text_group",
        {"target_ids": ["event_info"], "reference_id": "title", "edge": edge},
        layout,
    )
    aligned = next(item for item in changed.elements if item.id == "event_info")
    assert aligned.box.x == pytest.approx({"left": 0.1, "center": 0.2, "right": 0.3}[edge])
    assert aligned.box.y == target.box.y and aligned.box.width == target.box.width
    assert aligned.content == target.content and aligned.font_size == target.font_size


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("set_text_opacity", {"target_ids": ["title"], "opacity": 0}),
        ("set_text_opacity", {"target_ids": ["title"], "opacity": float("nan")}),
        ("set_text_opacity", {"target_ids": ["title", "title"], "opacity": 0.5}),
        ("set_text_opacity", {"target_ids": ["main_visual"], "opacity": 0.5}),
        ("set_text_opacity", {"target_ids": ["unknown"], "opacity": 0.5}),
        ("set_text_opacity", {"target_ids": ["title"], "opacity": 0.5, "execute": "anything"}),
        ("align_text_group", {"target_ids": ["title"], "reference_id": "title", "edge": "left"}),
        (
            "align_text_group",
            {"target_ids": ["title"], "reference_id": "main_visual", "edge": "left"},
        ),
    ],
)
def test_invalid_or_non_text_targets_are_rejected(name, arguments):
    layout = make_layout()
    before = layout.model_dump()
    with pytest.raises(ValueError):
        apply(name, arguments, layout)
    assert layout.model_dump() == before


def test_text_and_position_locks_block_extensions():
    with pytest.raises(DesignConstraintError):
        apply(
            "set_text_opacity",
            {"target_ids": ["title"], "opacity": 0.5},
            controls=DesignControls(
                locks=[{"element_id": "title", "properties": ["typography"]}],
            ),
        )
    layout = make_layout()
    target = next(item for item in layout.elements if item.id == "event_info")
    target.box = NormalizedBox(x=0.3, y=0.7, width=0.4, height=0.1)
    with pytest.raises(DesignConstraintError):
        apply(
            "align_text_group",
            {"target_ids": ["event_info"], "reference_id": "title"},
            layout,
            DesignControls(locks=[{"element_id": "event_info", "properties": ["position"]}]),
        )


def test_alignment_that_would_exceed_canvas_is_rejected():
    layout = make_layout()
    title = next(item for item in layout.elements if item.id == "title")
    title.box = NormalizedBox(x=0, y=0.1, width=0.1, height=0.1)
    with pytest.raises(ValueError):
        apply(
            "align_text_group",
            {"target_ids": ["event_info"], "reference_id": "title", "edge": "right"},
            layout,
        )
