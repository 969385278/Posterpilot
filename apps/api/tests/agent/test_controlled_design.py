import base64
import io
import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.agent.executor import LangGraphAgentExecutor
from app.agent.nodes.evaluate import EvaluationDependencies
from app.evaluation.deepgaze_client import DeepGazePrediction
from app.poster.renderer import PosterRenderer
from app.providers.image.base import GeneratedImage
from app.schemas.design_control import DesignControls
from app.schemas.evaluation import AttentionPrediction, Fixation, VisionReview
from app.schemas.layout import NormalizedBox
from app.poster.layout_candidates import propose_layouts
from tests.poster.test_action_validator import make_layout
from app.schemas.react import HumanDecision
from tests.agent.test_generation_nodes import FakeTextProvider, _brief
from tests.agent.test_hitl_executor import BothStageRetriever, DesignAndReactProvider
from tests.poster.test_design_controls import gradient_image


class GradientProvider:
    async def generate(self, prompt, **kwargs):
        buffer = io.BytesIO()
        gradient_image().save(buffer, format="PNG")
        return GeneratedImage(image_url="data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(), provider="test-fixture", model="deterministic-gradient")


class AttentionFixture:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    async def predict(self, *, image_bytes, filename, steps):
        self.calls.append(filename)
        assert image_bytes.startswith(b"\x89PNG")
        if len(self.calls) == self.fail_on:
            return DeepGazePrediction("unavailable", AttentionPrediction(availability="unavailable", error="fixture failure"), None)
        return DeepGazePrediction("available", AttentionPrediction(availability="available", model="fixture-not-deepgaze", fixations=[Fixation(x=0.2, y=0.1, order=1), Fixation(x=0.2, y=0.76, order=2)]), None)


class WholeImageSubject:
    async def evaluate(self, **kwargs):
        return VisionReview(availability="available", score=60, subject_regions=[NormalizedBox(x=0, y=0, width=1, height=1)])


def test_subject_aware_side_bands_keep_image_and_facts_and_honor_position_locks():
    original = make_layout()
    subject = NormalizedBox(x=0.36, y=0.4, width=0.28, height=0.5)
    candidates = propose_layouts(original, DesignControls(), [subject])
    side = [(name, candidate) for name, candidate in candidates if "主体" in name]
    assert len(side) == 2
    for name, candidate in side:
        assert [item.content for item in candidate.elements] == [item.content for item in original.elements]
        for item, old in zip(candidate.elements, original.elements):
            if item.role not in {"event_info", "organizer"}:
                assert item == old
            elif "左侧" in name:
                assert item.box.x + item.box.width < subject.x
            else:
                assert item.box.x > subject.x + subject.width
    locks = DesignControls(locks=[{"element_id": item.id, "properties": ["position"]} for item in original.elements if item.role in {"event_info", "organizer"}])
    assert not any("主体" in name for name, _ in propose_layouts(original, locks, [subject]))


def executor(path=None, *, provider=None, attention=None, vision=None):
    return LangGraphAgentExecutor(retriever=BothStageRetriever(), text_provider=provider or DesignAndReactProvider(), image_provider=GradientProvider(), renderer=PosterRenderer(), evaluation=EvaluationDependencies(deepgaze=attention, vision=vision), checkpoint_path=path)


async def test_title_only_brief_renders_candidates_and_finishes_native_hitl(tmp_path):
    from app.schemas.brief import PosterBrief
    agent = executor(attention=AttentionFixture())
    run_id = uuid4()
    brief = PosterBrief(title="摄影社招新")
    try:
        outcome = await agent.start(brief, run_id=run_id, run_directory=tmp_path)
        checkpoint = outcome.checkpoint
        assert {element["role"] for element in checkpoint.layout["elements"]} == {"title", "main_visual"}
        assert [fact.content for fact in checkpoint.analysis.text_facts] == ["摄影社招新"]
        assert checkpoint.layout_candidates
        for candidate in checkpoint.layout_candidates:
            assert {element.role for element in candidate.layout.elements} == {"title", "main_visual"}
        assert (tmp_path / checkpoint.poster_artifact).exists()
        finished = await agent.resume(run_id, HumanDecision(action="finish"), run_directory=tmp_path)
        assert finished.status == "completed"
    finally:
        await agent.aclose()


async def test_attention_candidates_render_current_image_and_use_comparable_signals(tmp_path: Path):
    attention = AttentionFixture()
    agent = executor(attention=attention)
    outcome = await agent.start(_brief(), run_id=uuid4(), run_directory=tmp_path)
    candidates = outcome.checkpoint.layout_candidates
    assert len(candidates) == 3
    assert len(attention.calls) == 3
    assert attention.calls[0] == "poster_initial.png"
    assert all(candidate.attention_used_for_ranking for candidate in candidates)
    assert sum(candidate.is_current for candidate in candidates) == 1
    assert outcome.checkpoint.rounds == []
    for candidate in candidates:
        assert (tmp_path / candidate.poster_artifact).is_file()
        assert candidate.analysis.text_facts
        assert all(check.status != "failed" for check in candidate.checks if check.key in {"text_fit", "layout_rules"})
        assert candidate.subject_overlap is None


async def test_one_attention_failure_downgrades_entire_candidate_ranking(tmp_path: Path):
    agent = executor(attention=AttentionFixture(fail_on=2))
    outcome = await agent.start(_brief(), run_id=uuid4(), run_directory=tmp_path)
    assert len(outcome.checkpoint.layout_candidates) >= 2
    assert not any(candidate.attention_used_for_ranking for candidate in outcome.checkpoint.layout_candidates)
    assert any(candidate.attention.availability == "unavailable" for candidate in outcome.checkpoint.layout_candidates)


async def test_known_subject_collisions_are_not_offered_as_alternatives(tmp_path: Path):
    agent = executor(attention=AttentionFixture(), vision=WholeImageSubject())
    outcome = await agent.start(_brief(), run_id=uuid4(), run_directory=tmp_path)
    assert len(outcome.checkpoint.layout_candidates) == 1
    assert outcome.checkpoint.layout_candidates[0].is_current
    assert outcome.checkpoint.layout_candidates[0].subject_overlap > 0.03


class NoExtraReact:
    async def complete_json(self, messages):
        assert "ReAct Agent" not in str(messages), "Explicit candidate selection must not add unrequested edits"
        return await FakeTextProvider().complete_json(messages)


async def test_candidate_selection_survives_sqlite_restart_and_saves_one_round(tmp_path: Path):
    checkpoint_db = tmp_path / "checkpoints.sqlite3"
    run_id = uuid4()
    first = executor(checkpoint_db, provider=NoExtraReact())
    started = await first.start(_brief(), run_id=run_id, run_directory=tmp_path)
    selected = next(candidate for candidate in started.checkpoint.layout_candidates if not candidate.is_current)
    await first.aclose()
    second = executor(checkpoint_db, provider=NoExtraReact())
    try:
        resumed = await second.resume(run_id, HumanDecision(action="instruct", controls=DesignControls(selected_candidate_id=selected.id)), run_directory=tmp_path)
        assert resumed.checkpoint.layout == selected.layout.model_dump(mode="json")
        assert len(resumed.checkpoint.rounds) == 1
        assert resumed.checkpoint.rounds[0].poster_artifact == "poster_round_1.png"
        assert resumed.checkpoint.rounds[0].tool_traces == []
        assert resumed.checkpoint.controls.selected_candidate_id is None
        assert all(candidate.round_number == 1 for candidate in resumed.checkpoint.layout_candidates)
    finally:
        await second.aclose()


class IgnoreLockThenAdjust:
    def __init__(self):
        self.calls = 0

    async def complete_json(self, messages):
        if "ReAct Agent" not in str(messages):
            return await FakeTextProvider().complete_json(messages)
        payload = json.loads(messages[-1]["content"])
        assert payload["design_controls"]["locks"][0]["element_id"] == "title"
        assert payload["measured_design_analysis"]["features"]
        self.calls += 1
        if self.calls == 1:
            return {"decision": "tool_call", "summary": "尝试违反锁定", "tool_name": "modify_typography", "arguments": {"actions": [{"action": "set_font_size", "target_id": "title", "parameters": {"font_size": 120}, "reason": "fixture"}]}}
        if self.calls == 2:
            assert payload["recent_tool_observations"][0]["success"] is False
            return {"decision": "tool_call", "summary": "按用户要求减弱背景反差", "tool_name": "adjust_background", "arguments": {"contrast": 0.7}}
        return {"decision": "finish_round", "summary": "进入本轮验证"}


async def test_lock_failure_observation_and_background_goal_survive_restart(tmp_path: Path):
    path = tmp_path / "checkpoint.sqlite3"
    run_id = uuid4()
    first = executor(path)
    started = await first.start(_brief(), run_id=run_id, run_directory=tmp_path)
    await first.aclose()
    second = executor(path, provider=IgnoreLockThenAdjust())
    controls = DesignControls(locks=[{"element_id": "title", "properties": ["position", "typography"]}], adjustments=[{"trait": "background_contrast", "direction": "weaken"}])
    try:
        resumed = await second.resume(run_id, HumanDecision(action="instruct", controls=controls), run_directory=tmp_path)
        checkpoint = resumed.checkpoint
        assert checkpoint.background_treatment.contrast == 0.7
        assert [trace.success for trace in checkpoint.tool_traces] == [False, True]
        assert checkpoint.round_number == 1
        before = next(fact for fact in started.checkpoint.analysis.text_facts if fact.element_id == "title")
        after = next(fact for fact in checkpoint.analysis.text_facts if fact.element_id == "title")
        assert before == after
        goal = next(check for check in checkpoint.goal_verification.checks if check.key == "background_contrast")
        assert goal.status == "passed"
        assert checkpoint.rounds[0].score_delta is None
        assert "目标" in checkpoint.rounds[0].comparison_reason
    finally:
        await second.aclose()


async def test_new_lock_cannot_be_bypassed_using_an_old_candidate(tmp_path: Path):
    agent = executor()
    run_id = uuid4()
    outcome = await agent.start(_brief(), run_id=run_id, run_directory=tmp_path)
    selected = next(candidate for candidate in outcome.checkpoint.layout_candidates if not candidate.is_current)
    controls = DesignControls(selected_candidate_id=selected.id, locks=[{"element_id": "title", "properties": ["position"]}])
    with pytest.raises(ValueError, match="锁定"):
        await agent.resume(run_id, HumanDecision(action="instruct", controls=controls), run_directory=tmp_path)


class ShrinkLockedText:
    async def complete_json(self, messages):
        if "ReAct Agent" not in str(messages):
            return await FakeTextProvider().complete_json(messages)
        traces = json.loads(messages[-1]["content"])["recent_tool_observations"]
        if not traces:
            return {"decision": "tool_call", "summary": "缩小文字区域但不直接改字号", "tool_name": "modify_layout", "arguments": {"actions": [{"action": "set_size", "target_id": "title", "parameters": {"width": 0.15, "height": 0.04}, "reason": "测试自动缩字的间接越权"}]}}
        if len(traces) == 1:
            return {"decision": "tool_call", "summary": "减弱背景", "tool_name": "adjust_background", "arguments": {"contrast": 0.8}}
        return {"decision": "finish_round", "summary": "测试渲染后保护"}


async def test_actual_font_change_rolls_back_entire_round_including_background(tmp_path: Path):
    agent = executor(provider=ShrinkLockedText())
    run_id = uuid4()
    initial = await agent.start(_brief(), run_id=run_id, run_directory=tmp_path)
    controls = DesignControls(locks=[{"element_id": "title", "properties": ["typography"]}], adjustments=[{"trait": "background_contrast", "direction": "weaken"}])
    outcome = await agent.resume(run_id, HumanDecision(action="instruct", controls=controls), run_directory=tmp_path)
    checkpoint = outcome.checkpoint
    assert checkpoint.layout == initial.checkpoint.layout
    assert checkpoint.background_treatment == initial.checkpoint.background_treatment
    assert checkpoint.analysis.text_facts == initial.checkpoint.analysis.text_facts
    assert checkpoint.goal_verification.outcome == "not_met"
    assert any(check.key == "render_guard" and check.status == "failed" for check in checkpoint.goal_verification.checks)
    assert any("锁定" in issue for issue in checkpoint.primary_issues)
    assert checkpoint.round_number == 1
    assert (tmp_path / "poster_initial.png").read_bytes() == (tmp_path / "poster_round_1.png").read_bytes()
