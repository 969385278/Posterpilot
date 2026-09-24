from uuid import UUID

import pytest

from app.agent.tools.react_tools import ReactToolRegistry, ReactToolValidationError
from app.core.exceptions import PosterPilotError
from app.schemas.react import ReactDecision
from app.schemas.tool_release import ToolReviewRequest
from tests.poster.test_action_validator import make_layout
from tests.services.test_user_memory import make_runs


def review(report_id=None, *, revision=0, action="publish"):
    return ToolReviewRequest(
        expected_revision=revision,
        action=action,
        reviewer="测试审查",
        note="核对实现与回归",
        report_id=report_id,
        implementation_reviewed=True,
    )


async def test_extensions_default_off_and_cannot_bypass_registry(tmp_path):
    registry = ReactToolRegistry(None)
    decision = ReactDecision(
        decision="tool_call",
        summary="测试",
        tool_name="set_text_opacity",
        arguments={"target_ids": ["title"], "opacity": 0.5},
    )
    with pytest.raises(ReactToolValidationError, match="not published"):
        await registry.execute(decision, layout=make_layout())
    registry.release_source = make_runs(tmp_path).harness
    with pytest.raises(PosterPilotError) as error:
        await registry.execute(decision, layout=make_layout())
    assert error.value.code == "tool_not_published"


def test_missing_failed_cancelled_and_wrong_tool_reports_cannot_publish(tmp_path):
    harness = make_runs(tmp_path).harness
    with pytest.raises(PosterPilotError) as error:
        harness.review("set_text_opacity", review())
    assert error.value.code == "review_required"
    report = harness.start_validation("set_text_opacity")
    with pytest.raises(PosterPilotError):
        harness.start_validation("align_text_group")
    with pytest.raises(PosterPilotError):
        harness.review("set_text_opacity", review(report["id"]))
    harness.cancel_validation(UUID(report["id"]))
    harness.run_validation(report["id"])
    assert harness.report(report["id"])["state"] == "cancelled"
    with pytest.raises(PosterPilotError):
        harness.review("set_text_opacity", review(report["id"]))


async def test_real_regression_report_publish_execute_withdraw_and_stale_code(
    tmp_path, monkeypatch
):
    """Real child pytest invocation; this file is deliberately outside the gate paths."""
    harness = make_runs(tmp_path).harness
    report = harness.start_validation("set_text_opacity")
    harness.run_validation(report["id"])
    report = harness.report(report["id"])
    assert report["state"] == "passed", report
    assert report["tests"] > 80 and report["failures"] == 0
    assert any("test_opacity_changes_rendered_pixels" in name for name in report["test_cases"])
    with pytest.raises(PosterPilotError):
        harness.review("align_text_group", review(report["id"]))
    released = harness.review("set_text_opacity", review(report["id"]))
    registry = ReactToolRegistry(None)
    registry.release_source = harness
    decision = ReactDecision(
        decision="tool_call",
        summary="测试已发布工具",
        tool_name="set_text_opacity",
        arguments={"target_ids": ["title"], "opacity": 0.5},
    )
    result = await registry.execute(decision, layout=make_layout())
    assert next(item for item in result.layout.elements if item.id == "title").opacity == 0.5
    assert result.publication["revision"] == released["revision"]
    # A released extension must satisfy the explicit goal through real rendering,
    # not just return a changed layout object or a successful tool trace.
    from app.agent.nodes.complete_round import render_round
    from app.agent.nodes.evaluate import evaluate_optimized
    from app.agent.nodes.execute_react_tool import execute_react_tool
    from app.poster.renderer import PosterRenderer
    from tests.evaluation.test_element_goals import prepare

    state = await prepare(tmp_path, [{"kind": "opacity", "element_id": "title", "opacity": 0.8}])
    state["react_decision"] = decision.model_copy(
        update={
            "arguments": {"target_ids": ["title"], "opacity": 0.8},
        }
    )
    state.update(await execute_react_tool(state, tools=registry))
    state.update(render_round(state, renderer=PosterRenderer(), run_directory=tmp_path))
    state.update(await evaluate_optimized(state, run_directory=tmp_path))
    assert state["goal_verification"].outcome == "met"
    assert state["tool_traces"][0].tool_publication["revision"] == released["revision"]
    # Both experimental arms use the actual publication, but the baseline cannot
    # invoke extensions. A shared no-op provider is a wiring test, not effect evidence.
    import json
    from uuid import uuid4

    from app.experiments.decisions import DecisionTask
    from app.experiments.toolsets import RestrictedToolset, compare_capabilities
    from tests.services.test_decision_experiment import FinishProvider

    task = DecisionTask(
        id="published-opacity",
        source_run_id=uuid4(),
        brief=state["brief"],
        design_spec=state["design_spec"],
        main_visual=state["main_visual_path"],
        instruction="标题不透明度设为80%",
        controls=state["design_controls"],
    )
    experiment = tmp_path / "toolset-experiment"
    summary, rows = await compare_capabilities(
        [task],
        experiment,
        provider=FinishProvider(),
        tools=registry,
        hub=harness.hub,
        added_tools=["set_text_opacity"],
        rounds=1,
    )
    assert summary["valid_execution"] and not summary["valid_live_comparison"]
    assert not summary["effect_claim_supported"]
    assert summary["paired_outcomes"]["newly_solved"] == 0
    assert all(item["censored"] for item in rows[0]["conditions"].values())
    assert (experiment / f"gate_report_{report['id']}.json").is_file()
    prompts = []
    for arm in ["base_tools", "extended_tools"]:
        recorded = json.loads((experiment / task.id / arm / "model_call_1.json").read_text("utf-8"))
        prompts.append(json.loads(recorded["messages"][-1]["content"]))
    assert "set_text_opacity" not in {item["name"] for item in prompts[0]["published_tool_catalog"]}
    assert "set_text_opacity" in {item["name"] for item in prompts[1]["published_tool_catalog"]}
    for prompt in prompts:
        assert prompt["decision_cards"] == []
        prompt.pop("published_tool_catalog")
    assert prompts[0] == prompts[1]
    old_fingerprint = harness.fingerprint()
    monkeypatch.setattr(harness, "fingerprint", lambda: "changed-code")
    with pytest.raises(PosterPilotError):
        await registry.execute(decision, layout=make_layout())
    monkeypatch.setattr(harness, "fingerprint", lambda: old_fingerprint)
    harness.review("set_text_opacity", review(revision=1, action="withdraw"))
    with pytest.raises(PosterPilotError):
        await RestrictedToolset(registry, {"set_text_opacity"}).execute(
            decision,
            layout=make_layout(),
        )
    with pytest.raises(PosterPilotError):
        await registry.execute(decision, layout=make_layout())
    with pytest.raises(PosterPilotError):
        harness.review("set_text_opacity", review(report["id"], revision=1))
