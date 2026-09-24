import pytest
from PIL import Image
from pydantic import ValidationError

from app.agent.nodes.complete_round import render_round
from app.agent.nodes.evaluate import evaluate_draft, evaluate_optimized
from app.agent.nodes.render_draft import render_draft
from app.agent.tools.extensions import execute_extension
from app.agent.tools.react_tools import ReactToolRegistry
from app.evaluation.element_goals import element_goal_checks
from app.poster.design_guards import DesignConstraintError, validate_control_targets
from app.poster.renderer import PosterRenderer
from app.schemas.design_control import DesignControls
from app.schemas.react import ReactDecision
from tests.agent.test_rendering_nodes import _state


async def prepare(tmp_path, goals):
    state = _state()
    for element in state["design_spec"].layout.elements:
        if element.content:
            element.color = "#111111"
    image = tmp_path / "visual.png"
    Image.new("RGB", (320, 480), "#FFFFFF").save(image)
    state.update(
        main_visual_path=str(image),
        layout=state["design_spec"].layout.model_copy(deep=True),
        design_controls=DesignControls(element_goals=goals),
        round_number=1,
    )
    state.update(render_draft(state, renderer=PosterRenderer(), run_directory=tmp_path))
    state.update(await evaluate_draft(state, run_directory=tmp_path))
    state.update(
        round_base_layout=state["layout"].model_copy(deep=True),
        round_base_treatment=state["background_treatment"].model_copy(deep=True),
        analysis_before_round=state["analysis_current"].model_copy(deep=True),
    )
    return state


async def test_opacity_goal_requires_actual_render_and_retains_readability_gate(tmp_path):
    state = await prepare(tmp_path, [{"kind": "opacity", "element_id": "title", "opacity": 0.8}])
    state["layout"], _ = execute_extension(
        "set_text_opacity",
        {"target_ids": ["title"], "opacity": 0.8},
        state["layout"],
        controls=state["design_controls"],
        baseline=state["round_base_layout"],
    )
    # Nominal layout changes without matching render evidence are not accepted.
    checks = element_goal_checks(
        state["design_controls"],
        state["round_base_layout"],
        state["layout"],
        state["analysis_before_round"],
        state["analysis_current"],
    )
    assert checks[0].status == "failed"
    state.update(render_round(state, renderer=PosterRenderer(), run_directory=tmp_path))
    state.update(await evaluate_optimized(state, run_directory=tmp_path))
    assert state["goal_verification"].outcome == "met"
    state["design_controls"] = DesignControls(
        element_goals=[
            {"kind": "opacity", "element_id": "title", "opacity": 0.3},
        ]
    )
    state["layout"].elements[0].opacity = 0.3
    state.update(render_round(state, renderer=PosterRenderer(), run_directory=tmp_path))
    state.update(await evaluate_optimized(state, run_directory=tmp_path))
    checks = {item.key: item.status for item in state["goal_verification"].checks}
    assert checks["element:opacity:title"] == "passed"
    assert checks["readability:title"] == "failed"
    assert state["goal_verification"].outcome == "not_met"


async def test_alignment_is_also_reachable_with_existing_layout_tool(tmp_path):
    state = await prepare(
        tmp_path,
        [
            {
                "kind": "alignment",
                "element_id": "event-info",
                "reference_id": "title",
                "edge": "right",
            }
        ],
    )
    elements = {item.id: item for item in state["layout"].elements}
    elements["event-info"].box.width = 0.6
    source = state["layout"].model_copy(deep=True)
    changed, _ = execute_extension(
        "align_text_group",
        {"target_ids": ["event-info"], "reference_id": "title", "edge": "right"},
        source,
        controls=state["design_controls"],
        baseline=source,
    )
    x = elements["title"].box.x + elements["title"].box.width - elements["event-info"].box.width
    result = await ReactToolRegistry(None).execute(
        ReactDecision(
            decision="tool_call",
            summary="原有工具对齐文字框",
            tool_name="modify_layout",
            arguments={
                "actions": [
                    {
                        "action": "set_position",
                        "target_id": "event-info",
                        "parameters": {"x": x, "y": elements["event-info"].box.y},
                        "reason": "相同右边",
                        "source_rule_ids": [],
                    }
                ]
            },
        ),
        layout=source,
        controls=state["design_controls"],
    )
    for actual, expected in zip(result.layout.elements, changed.elements, strict=True):
        assert actual.model_dump(exclude={"box"}) == expected.model_dump(exclude={"box"})
        assert actual.box.model_dump() == pytest.approx(expected.box.model_dump())
    state["layout"] = result.layout
    state.update(render_round(state, renderer=PosterRenderer(), run_directory=tmp_path))
    state.update(await evaluate_optimized(state, run_directory=tmp_path))
    assert (
        next(
            item
            for item in state["goal_verification"].checks
            if item.key == "element:alignment:event-info"
        ).status
        == "passed"
    )


def test_element_goals_reject_unknown_nontext_duplicate_and_self_reference():
    layout = _state()["design_spec"].layout
    for target in ["missing", "visual"]:
        with pytest.raises(DesignConstraintError):
            validate_control_targets(
                DesignControls(
                    element_goals=[
                        {"kind": "opacity", "element_id": target, "opacity": 0.8},
                    ]
                ),
                layout,
            )
    with pytest.raises(ValidationError):
        DesignControls(
            element_goals=[
                {
                    "kind": "alignment",
                    "element_id": "title",
                    "reference_id": "title",
                    "edge": "left",
                }
            ]
        )


async def test_selected_candidate_does_not_skip_explicit_element_goal(tmp_path):
    from app.agent.nodes.react_decide import react_decide
    from app.schemas.react import HumanDecision

    class Provider:
        calls = 0

        async def complete_json(self, messages):
            self.calls += 1
            return {"decision": "finish_round", "summary": "记录实际模型分支"}

    state = await prepare(tmp_path, [{"kind": "opacity", "element_id": "title", "opacity": 0.8}])
    state["design_controls"].selected_candidate_id = "candidate"
    state["human_decision"] = HumanDecision(action="instruct", controls=state["design_controls"])
    provider = Provider()
    await react_decide(state, text_provider=provider)
    assert provider.calls == 1
    with pytest.raises(ValidationError):
        DesignControls(
            element_goals=[
                {"kind": "opacity", "element_id": "title", "opacity": 0.8},
                {"kind": "opacity", "element_id": "title", "opacity": 0.9},
            ]
        )
