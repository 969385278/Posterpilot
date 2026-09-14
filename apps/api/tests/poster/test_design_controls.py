from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageStat
from pydantic import ValidationError

from app.agent.tools.react_tools import ReactToolRegistry
from app.evaluation.design_analysis import analyze_design
from app.evaluation.goal_verifier import verify_design_goals
from app.poster.color_treatment import treat_background
from app.poster.design_guards import DesignConstraintError, assert_design_constraints
from app.poster.renderer import PosterRenderer
from app.schemas.design_control import BackgroundTreatment, DesignControls, ReferenceSelection
from app.schemas.react import HumanDecision
from tests.agent.test_react_tools import FakeRetriever, _decision
from tests.poster.test_renderer import make_layout


def gradient_image() -> Image.Image:
    image = Image.new("RGB", (120, 160))
    draw = ImageDraw.Draw(image)
    for x in range(120):
        draw.line((x, 0, x, 160), fill=(40 + x, 30 + x, 60 + x))
    return image


@pytest.mark.parametrize("payload", [
    {"adjustments": [{"trait": "background_contrast", "direction": "weaken"}] * 2},
    {"locks": [{"element_id": "title", "properties": ["position", "position"]}]},
    {"attention_priority": ["title", "title"]},
    {"adjustments": [{"trait": "background_contrast", "direction": "remove"}]},
    {"adjustments": [{"trait": "background_contrast", "direction": "weaken", "strength": float("nan")}]},
    {"ignore_locks": True},
])
def test_controls_reject_ambiguous_or_unsupported_requests(payload):
    with pytest.raises(ValidationError):
        DesignControls.model_validate(payload)


def test_reference_choice_requires_exact_safe_id_and_aspects():
    with pytest.raises(ValidationError):
        ReferenceSelection(case_id="../../private", aspects=["palette"])
    with pytest.raises(ValidationError):
        ReferenceSelection(case_id="sample", aspects=[])
    assert ReferenceSelection(case_id="sample", aspects=["palette"]).case_id == "sample"


def test_structured_instruction_does_not_require_retyping_prompt():
    controls = DesignControls(adjustments=[{"trait": "background_contrast", "direction": "weaken"}])
    assert HumanDecision(action="instruct", controls=controls).instruction is None
    with pytest.raises(ValidationError):
        HumanDecision(action="finish", controls=controls)


def test_treatment_preserves_source_and_geometry():
    source = gradient_image()
    original = source.copy()
    changed = treat_background(source, BackgroundTreatment(contrast=0.6))
    assert ImageChops.difference(source, original).getbbox() is None
    assert changed.size == source.size
    assert ImageStat.Stat(changed.convert("L")).stddev[0] < ImageStat.Stat(source.convert("L")).stddev[0]
    assert ImageChops.difference(changed, treat_background(source, BackgroundTreatment(contrast=0.6))).getbbox() is None


def test_saturation_is_not_contrast():
    source = gradient_image()
    changed = treat_background(source, BackgroundTreatment(saturation=0))
    assert ImageStat.Stat(changed.convert("HSV").getchannel("S")).mean[0] == 0
    assert ImageStat.Stat(changed.convert("L")).stddev[0] > 0


@pytest.mark.parametrize("change", ["content", "main_visual", "order"])
def test_immutable_facts_geometry_and_paint_order(change):
    before = make_layout()
    after = before.model_copy(deep=True)
    if change == "content":
        after.elements[0].content = "虚构日期"
    elif change == "main_visual":
        next(item for item in after.elements if item.role == "main_visual").opacity = 0.3
    else:
        after.elements.reverse()
    with pytest.raises(DesignConstraintError):
        assert_design_constraints(before, after, DesignControls())


async def test_locked_typography_is_enforced_by_tool_not_prompt():
    layout = make_layout()
    snapshot = layout.model_dump()
    controls = DesignControls(locks=[{"element_id": "title", "properties": ["typography"]}])
    decision = _decision("modify_typography", {"actions": [{"action": "set_font_size", "target_id": "title", "parameters": {"font_size": 120}, "reason": "模型忽略锁定"}]})
    with pytest.raises(DesignConstraintError, match="锁定"):
        await ReactToolRegistry(FakeRetriever()).execute(decision, layout=layout, controls=controls)
    assert layout.model_dump() == snapshot


async def test_background_preserve_rejects_tool_and_other_factor_survives():
    registry = ReactToolRegistry(FakeRetriever())
    controls = DesignControls(adjustments=[{"trait": "background_contrast", "direction": "preserve"}])
    with pytest.raises(DesignConstraintError, match="保留"):
        await registry.execute(_decision("adjust_background", {"contrast": 0.8}), layout=make_layout(), controls=controls)
    result = await registry.execute(_decision("adjust_background", {"saturation": 0.7}), layout=make_layout(), controls=controls, treatment=BackgroundTreatment(contrast=1.2))
    assert result.treatment == BackgroundTreatment(contrast=1.2, saturation=0.7)


@pytest.mark.parametrize("arguments", [{}, {"contrast": 10}, {"contrast": 0.8, "path": "private.png"}, {"saturation": float("inf")}])
async def test_background_tool_rejects_unsafe_arguments(arguments):
    with pytest.raises(ValidationError):
        await ReactToolRegistry(FakeRetriever()).execute(_decision("adjust_background", arguments), layout=make_layout())


def test_analysis_records_actual_font_and_measured_direction(tmp_path: Path):
    source = tmp_path / "source.png"
    gradient_image().save(source)
    layout = make_layout()
    renderer = PosterRenderer()
    before_render = renderer.render(layout, main_visual_path=source, output_path=tmp_path / "before.png", background_color="#FFFFFF")
    treatment = BackgroundTreatment(contrast=0.7)
    after_render = renderer.render(layout, main_visual_path=source, output_path=tmp_path / "after.png", background_color="#FFFFFF", treatment=treatment)
    assert before_render.text_facts == after_render.text_facts
    assert all(fact.font_name and fact.actual_font_size <= fact.requested_font_size for fact in before_render.text_facts)
    before = analyze_design(layout, main_visual_path=source, treatment=BackgroundTreatment(), text_facts=before_render.text_facts)
    after = analyze_design(layout, main_visual_path=source, treatment=treatment, text_facts=after_render.text_facts)
    controls = DesignControls(adjustments=[{"trait": "background_contrast", "direction": "weaken"}])
    report = verify_design_goals(before_layout=layout, after_layout=layout, before_analysis=before, after_analysis=after, controls=controls, before_treatment=BackgroundTreatment(), after_treatment=treatment)
    goal = next(check for check in report.checks if check.key == "background_contrast")
    assert goal.status == "passed"
    assert goal.after < goal.before
    unchanged = verify_design_goals(before_layout=layout, after_layout=layout, before_analysis=before, after_analysis=before, controls=controls, before_treatment=BackgroundTreatment(), after_treatment=BackgroundTreatment())
    assert unchanged.outcome == "not_met"


def test_renderer_reports_actual_shrinking_and_accepts_small_requested_font(tmp_path: Path):
    source = tmp_path / "source.png"
    gradient_image().save(source)
    layout = make_layout()
    title = next(element for element in layout.elements if element.role == "title")
    title.font_size = 200
    result = PosterRenderer().render(layout, main_visual_path=source, output_path=tmp_path / "large.png", background_color="#FFFFFF")
    fact = next(fact for fact in result.text_facts if fact.element_id == title.id)
    assert fact.actual_font_size < fact.requested_font_size
    title.font_size = 10
    small = PosterRenderer().render(layout, main_visual_path=source, output_path=tmp_path / "small.png", background_color="#FFFFFF")
    assert next(fact for fact in small.text_facts if fact.element_id == title.id).actual_font_size == 10
