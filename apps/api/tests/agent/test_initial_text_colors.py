from pathlib import Path

import pytest
from PIL import Image, ImageChops

from app.agent.nodes.render_draft import render_draft
from app.evaluation.readability import text_readability_checks
from app.poster.renderer import PosterRenderer
from app.schemas.design_control import BackgroundTreatment, DesignControls, ElementLock
from tests.agent.test_rendering_nodes import _state


@pytest.mark.parametrize("background", ["#FFFFFF", "#080808"])
def test_initial_render_uses_actual_background_and_persists_color(tmp_path, background):
    state = _state()
    image = tmp_path / "background.png"
    Image.new("RGB", (1080, 1440), background).save(image)
    state["main_visual_path"] = str(image)
    before = state["design_spec"].layout.model_copy(deep=True)
    renderer = PosterRenderer()
    baseline = tmp_path / "baseline.png"
    renderer.render(
        before, main_visual_path=image, output_path=baseline, background_color=background
    )
    result = render_draft(state, renderer=renderer, run_directory=tmp_path)
    assert state["design_spec"].layout == before  # no in-place state mutation
    assert result["layout"] == result["design_spec"].layout
    checks = text_readability_checks(
        result["layout"],
        main_visual_path=image,
        treatment=BackgroundTreatment(),
        text_facts=result["rendered_text_facts"],
    )
    assert checks and all(check.status == "passed" for check in checks)
    for original, current in zip(before.elements, result["layout"].elements, strict=True):
        assert original.model_dump(exclude={"color"}) == current.model_dump(exclude={"color"})
    facts = {fact.element_id: fact for fact in result["rendered_text_facts"]}
    for element in result["layout"].elements:
        if element.content:
            assert facts[element.id].color == (element.color or "#F8FAFC")
    with Image.open(baseline) as old, Image.open(result["poster_initial_path"]) as new:
        changed = ImageChops.difference(old, new).getbbox()
    adjustments = result["events"][-1]["payload"]["initial_color_adjustments"]
    if background == "#FFFFFF":
        assert changed and adjustments
    else:
        assert changed is None and adjustments == []
    # Subsequent rendering follows persisted colors exactly; it has no auto repair.
    later = result["layout"].model_copy(deep=True)
    later.elements[0].color = "#FFFFFF"
    later.elements[0].opacity = 0.8
    edited = renderer.render(
        later,
        main_visual_path=image,
        output_path=tmp_path / "edited.png",
        background_color=background,
    )
    assert edited.text_facts[0].color == "#FFFFFF"
    assert edited.text_facts[0].opacity == 0.8


def test_initial_color_selection_preserves_typography_lock(tmp_path: Path):
    state = _state()
    image = tmp_path / "background.png"
    Image.new("RGB", (1080, 1440), "white").save(image)
    state["main_visual_path"] = str(image)
    state["design_controls"] = DesignControls(
        locks=[ElementLock(element_id="title", properties=["typography"])]
    )
    original = state["design_spec"].layout.elements[0].model_copy(deep=True)
    result = render_draft(state, renderer=PosterRenderer(), run_directory=tmp_path)
    assert result["layout"].elements[0] == original
    assert all(
        row["element_id"] != "title"
        for row in result["events"][-1]["payload"]["initial_color_adjustments"]
    )


def test_initial_scrim_choice_persists_and_edits_cannot_switch_it(tmp_path):
    from PIL import ImageDraw

    from app.poster.design_guards import DesignConstraintError, assert_design_constraints
    from app.schemas.layout import PosterLayout

    state = _state()
    image = tmp_path / "mixed.png"
    source = Image.new("RGB", (1080, 1440), "white")
    ImageDraw.Draw(source).rectangle((0, 0, 539, 1439), fill=(120, 120, 120))
    source.save(image)
    state["main_visual_path"] = str(image)
    result = render_draft(state, renderer=PosterRenderer(), run_directory=tmp_path)
    layout = result["layout"]
    assert layout.readability_scrims is False
    restored = PosterLayout.model_validate_json(layout.model_dump_json())
    assert restored.readability_scrims is False
    checks = text_readability_checks(
        restored,
        main_visual_path=image,
        treatment=BackgroundTreatment(),
        text_facts=result["rendered_text_facts"],
    )
    assert all(check.status == "passed" for check in checks)
    with pytest.raises(DesignConstraintError, match="渐变模式"):
        assert_design_constraints(
            restored, restored.model_copy(update={"readability_scrims": True}), DesignControls()
        )
    legacy = layout.model_dump(exclude={"readability_scrims"})
    assert PosterLayout.model_validate(legacy).readability_scrims is True
