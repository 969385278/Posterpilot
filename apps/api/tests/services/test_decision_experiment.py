import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image

from app.agent.tools.react_tools import ReactToolRegistry
from app.experiments.decisions import DecisionTask, compare_decisions
from app.schemas.design_control import DesignControls
from tests.agent.test_rendering_nodes import _state


def make_task(tmp_path):
    state = _state()
    image = tmp_path / "input.png"
    Image.new("RGB", (320, 480), "#CBAA84").save(image)
    return DecisionTask(
        id="title",
        source_run_id=uuid4(),
        brief=state["brief"],
        design_spec=state["design_spec"],
        main_visual=image,
        instruction="增强标题",
        controls=DesignControls.model_validate(
            {
                "adjustments": [
                    {"trait": "title_emphasis", "direction": "strengthen", "strength": 0.1}
                ],
            }
        ),
    )


def hub():
    return SimpleNamespace(
        include_demo=False,
        retrieve=lambda query: [{"case_id": "same-experience"}],
        decisions=SimpleNamespace(retrieve=lambda state, **kwargs: [{"card_id": "fixture-card"}]),
    )


class FinishProvider:
    async def complete_json(self, messages):
        return {"decision": "finish_round", "summary": "测试结束，无修改"}


async def test_pair_keeps_context_and_initial_pixels_and_censors_unsolved(tmp_path):
    task = make_task(tmp_path)
    root = tmp_path / "comparison"
    summary, rows = await compare_decisions(
        [task],
        root,
        provider=FinishProvider(),
        tools=ReactToolRegistry(None),
        hub=hub(),
    )
    assert summary["valid_execution"]
    assert not summary["effect_claim_supported"]
    for condition in summary["conditions"].values():
        assert condition["unresolved_or_error"] == 1
        assert condition["mean_rounds_successes_only"] is None
    assert all(item["first_action"] is None for item in rows[0]["conditions"].values())
    messages = []
    for arm in ["without_cards", "with_cards"]:
        evidence = json.loads((root / "title" / arm / "experience_round_1.json").read_text("utf-8"))
        assert evidence["experience_references"] == [{"case_id": "same-experience"}]
        assert len(evidence["decision_card_references"]) == (arm == "with_cards")
        messages.append(
            json.loads((root / "title" / arm / "model_call_1.json").read_text("utf-8"))["messages"]
        )
    assert messages[0] != messages[1]
    prompts = [json.loads(item[-1]["content"]) for item in messages]
    for prompt in prompts:
        prompt.pop("decision_cards")
    assert prompts[0] == prompts[1]
    with pytest.raises(FileExistsError):
        await compare_decisions(
            [task], root, provider=FinishProvider(), tools=ReactToolRegistry(None), hub=hub()
        )


class RepeatedToolProvider:
    async def complete_json(self, messages):
        return {
            "decision": "tool_call",
            "summary": "测试固定字号",
            "tool_name": "modify_typography",
            "arguments": {
                "actions": [
                    {
                        "action": "set_font_size",
                        "target_id": "title",
                        "parameters": {"font_size": 90},
                        "reason": "测试",
                        "source_rule_ids": [],
                    }
                ]
            },
        }


async def test_real_tools_budget_and_first_probe_does_not_enter_model_context(tmp_path):
    task = make_task(tmp_path)
    summary, rows = await compare_decisions(
        [task],
        tmp_path / "pair",
        provider=RepeatedToolProvider(),
        tools=ReactToolRegistry(None),
        hub=hub(),
        rounds=1,
    )
    assert summary["valid_execution"]
    for arm, outcome in rows[0]["conditions"].items():
        assert outcome["model_calls"] == 2
        assert outcome["first_action"]["trace"]["success"]
        assert len(outcome["rounds"][0]["snapshot"]["tool_traces"]) == 1
        call = json.loads(
            (tmp_path / "pair" / "title" / arm / "model_call_2.json").read_text("utf-8")
        )
        first = json.loads(
            (tmp_path / "pair" / "title" / arm / "model_call_1.json").read_text("utf-8")
        )
        # The probe never becomes model evidence; obsolete measurements are
        # withheld after the mutation until the next production render.
        user1 = json.loads(first["messages"][-1]["content"])
        user2 = json.loads(call["messages"][-1]["content"])
        assert user1["measured_design_analysis"]
        assert user2["measured_design_analysis"] == {}


async def test_provider_errors_stay_in_denominator_and_raw_requests_are_saved(tmp_path):
    class Broken:
        async def complete_json(self, messages):
            raise TimeoutError("unavailable")

    summary, rows = await compare_decisions(
        [make_task(tmp_path)],
        tmp_path / "pair",
        provider=Broken(),
        tools=ReactToolRegistry(None),
        hub=hub(),
    )
    assert not summary["valid_execution"]
    assert summary["runtime_error_tasks"] == 1
    assert summary["conditions"]["with_cards"]["unresolved_or_error"] == 1
    assert rows[0]["conditions"]["with_cards"]["error_type"] == "TimeoutError"
    record = json.loads((tmp_path / "pair/title/with_cards/model_call_1.json").read_text("utf-8"))
    assert record["messages"] and record["error_type"] == "TimeoutError"


async def test_context_drift_invalidates_completed_pair(tmp_path):
    source = hub()
    calls = 0

    def changing_cards(state, **kwargs):
        nonlocal calls
        calls += 1
        return [{"card_id": "fixture-card", "revision": calls}]

    source.decisions.retrieve = changing_cards
    summary, _ = await compare_decisions(
        [make_task(tmp_path)],
        tmp_path / "pair",
        provider=FinishProvider(),
        tools=ReactToolRegistry(None),
        hub=source,
        rounds=1,
    )
    assert summary["context_or_catalog_drift"]
    assert not summary["valid_execution"]


async def test_missing_initial_image_is_counted_and_does_not_call_model(tmp_path):
    task = make_task(tmp_path)
    task.main_visual = tmp_path / "missing.png"
    summary, rows = await compare_decisions(
        [task],
        tmp_path / "pair",
        provider=FinishProvider(),
        tools=ReactToolRegistry(None),
        hub=hub(),
    )
    assert summary["runtime_error_tasks"] == 1
    assert summary["conditions"]["with_cards"]["unresolved_or_error"] == 1
    assert not rows[0]["conditions"]


async def test_success_is_measured_from_real_rendered_goal_in_both_arms(tmp_path):
    class Enlarge(RepeatedToolProvider):
        async def complete_json(self, messages):
            decision = await super().complete_json(messages)
            decision["arguments"]["actions"][0]["parameters"]["font_size"] = 110
            return decision

    task = make_task(tmp_path)
    # This positive fixture isolates title size; give all text adequate contrast.
    for element in task.design_spec.layout.elements:
        if element.role != "main_visual":
            element.color = "#111111"
    summary, rows = await compare_decisions(
        [task],
        tmp_path / "pair",
        provider=Enlarge(),
        tools=ReactToolRegistry(None),
        hub=hub(),
    )
    assert summary["valid_execution"]
    for arm in rows[0]["conditions"].values():
        assert arm["first_action"]["accepted"]
        assert arm["accepted_round"] == 1
    assert not summary["effect_claim_supported"]
