from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.brief import PosterBrief
from app.schemas.intent import IntentRequest
from app.services.intent_router import (
    Classification,
    IntentRouter,
    RuleIntentClassifier,
    parse_local_requirements,
)
from tests.services.test_user_memory import make_runs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("生成一张海报，标题：社团招新", "generate"),
        ("放大标题，背景更柔和", "modify"),
        ("怎么生成海报？", "question"),
        ("如何放大标题？", "question"),
        ("嗯，再弄弄", "clarify"),
    ],
)
async def test_rules_preserve_question_intent(text, expected):
    assert (await RuleIntentClassifier().classify(text)).label == expected


def test_compound_requirements_keep_locks_and_goals_separate():
    requirements, controls = parse_local_requirements("放大标题，降低背景饱和度，时间地点位置不变")
    assert len(requirements) == 3
    assert controls.locks[0].element_id == "event_info"
    assert controls.locks[0].properties == ["position"]
    assert {(item.trait, item.direction) for item in controls.adjustments} == {
        ("title_emphasis", "strengthen"),
        ("background_saturation", "weaken"),
    }
    _, negative = parse_local_requirements("不要放大标题")
    assert negative.adjustments == []
    assert "typography" in negative.locks[0].properties


@pytest.mark.parametrize("clause, expected", [
    ("标题的位置和字号不变", {"position", "typography"}),
    ("标题字号不变", {"typography"}),
    ("标题位置和内容不变", {"position", "content"}),
    ("时间地点尺寸、颜色和文案保持不变", {"position", "typography", "content"}),
])
def test_compound_lock_properties_are_enforced(clause, expected):
    from app.poster.design_guards import DesignConstraintError, assert_design_constraints
    from tests.poster.test_action_validator import make_layout

    _, controls = parse_local_requirements(clause)
    lock = controls.locks[0]
    assert set(lock.properties) == expected
    original = make_layout()
    changed = original.model_copy(deep=True)
    target = next(item for item in changed.elements if item.id == lock.element_id)
    if "typography" in expected:
        target.font_size += 1
    else:
        target.content += " changed"
    with pytest.raises(DesignConstraintError):
        assert_design_constraints(original, changed, controls)


def test_explicit_opacity_goal_is_grounded_and_conflicting_values_are_rejected():
    _, controls = parse_local_requirements("标题不透明度设为80%，时间地点位置不变")
    assert controls.element_goals[0].opacity == 0.8
    assert controls.element_goals[0].element_id == "title"
    with pytest.raises(ValueError):
        parse_local_requirements("标题不透明度80%，标题不透明度60%")
    with pytest.raises(ValueError):
        parse_local_requirements("标题不透明度120%")


def test_conjunctions_background_preservation_and_lock_union():
    _, controls = parse_local_requirements("放大标题但保持时间地点位置不变")
    assert [lock.element_id for lock in controls.locks] == ["event_info"]
    assert controls.adjustments[0].direction == "strengthen"
    _, controls = parse_local_requirements("背景保持不变")
    assert {item.trait for item in controls.adjustments} == {
        "background_contrast",
        "background_saturation",
    }
    assert all(item.direction == "preserve" for item in controls.adjustments)
    _, controls = parse_local_requirements("标题保持不变，标题位置不变")
    assert set(controls.locks[0].properties) == {"content", "position", "typography"}
    _, controls = parse_local_requirements("标题和副标题位置不变")
    assert {lock.element_id for lock in controls.locks} == {"title", "subtitle"}


async def test_conflicting_directions_require_clarification(tmp_path):
    runs = make_runs(tmp_path)
    result = await IntentRouter(runs).resolve(
        IntentRequest(text="降低背景饱和度，同时提高背景饱和度")
    )
    assert result.intent == "clarify" and not result.can_apply
    assert "冲突" in result.explanation


@pytest.mark.asyncio
async def test_confident_route_never_calls_llm_and_does_not_create_run(tmp_path):
    runs = make_runs(tmp_path)

    class FailIfCalled:
        async def complete_json(self, messages):
            raise AssertionError("high confidence must skip model")

    runs.executor = SimpleNamespace(text_provider=FailIfCalled())
    result = await IntentRouter(runs).resolve(IntentRequest(text="制作一张海报，标题：春日市集"))
    assert result.intent == "generate" and not result.fallback_used
    assert result.brief.title == "春日市集"
    assert result.brief.event_time == ""
    assert result.needs_confirmation and not result.can_apply
    assert runs.repository.list() == []


@pytest.mark.asyncio
async def test_low_confidence_calls_fallback_and_missing_provider_is_honest(tmp_path):
    runs = make_runs(tmp_path)
    result = await IntentRouter(runs).resolve(IntentRequest(text="嗯，再弄弄"))
    assert result.intent == "clarify" and result.route_method == "unavailable"

    class Provider:
        async def complete_json(self, messages):
            return {"intent": "question", "explanation": "在询问设计建议"}

    runs.executor = SimpleNamespace(text_provider=Provider())
    result = await IntentRouter(runs).resolve(IntentRequest(text="帮我看看色彩是不是太杂"))
    assert result.fallback_used and result.route_method == "llm_fallback"
    assert result.intent == "question"


@pytest.mark.asyncio
async def test_fallback_cannot_invent_facts_or_constraints(tmp_path):
    runs = make_runs(tmp_path)

    class LowConfidence:
        async def classify(self, text):
            return Classification("generate", 0.4, "test-classifier")

    class Provider:
        async def complete_json(self, messages):
            return {"intent": "generate", "brief": {"title": "虚构的标题", "event_time": "明天"}}

    runs.executor = SimpleNamespace(text_provider=Provider())
    result = await IntentRouter(runs, classifier=LowConfidence()).resolve(
        IntentRequest(text="做个宣传页")
    )
    assert result.intent == "clarify" and result.brief is None


def test_endpoint_preview_does_not_mutate_existing_run(tmp_path):
    runs = make_runs(tmp_path)
    run = runs.create(PosterBrief(title="现有海报"))
    client = TestClient(create_app(runs))
    response = client.post(
        "/api/v1/intents/resolve", json={"text": "放大标题", "run_id": str(run.id)}
    )
    assert response.status_code == 200 and not response.json()["can_apply"]
    assert runs.get(run.id).status == "queued"


@pytest.mark.asyncio
async def test_routing_carries_previous_locks_and_binds_preview_to_round(tmp_path):
    from app.poster.template_loader import TemplateLoader
    from app.schemas.react import HumanCheckpoint

    runs = make_runs(tmp_path)
    runs.executor = SimpleNamespace()
    brief = PosterBrief(title="测试活动", event_time="周末")
    run = runs.create(brief)
    runs.repository.update_status(run.id, "waiting_for_human")
    pending = HumanCheckpoint(
        round_number=1,
        score=60,
        suggestion="检查海报",
        layout=TemplateLoader().instantiate(brief.poster_type, brief).model_dump(mode="json"),
        controls={
            "locks": [{"element_id": "event_info", "properties": ["position"]}],
            "element_goals": [{"kind": "opacity", "element_id": "title", "opacity": 0.8}],
        },
    )
    runs.artifacts.write_json(run.id, "pending_human.json", pending.model_dump(mode="json"))
    result = await IntentRouter(runs).resolve(IntentRequest(text="放大标题", run_id=run.id))
    assert result.can_apply and result.round_number == 1
    assert result.controls.locks[0].element_id == "event_info"
    assert result.controls.locks[0].properties == ["position"]
    assert result.controls.adjustments[0].trait == "title_emphasis"
    assert result.controls.element_goals[0].opacity == 0.8
    result = await IntentRouter(runs).resolve(IntentRequest(text="标题不透明度60%", run_id=run.id))
    assert result.can_apply and result.controls.element_goals[0].opacity == 0.6
    result = await IntentRouter(runs).resolve(
        IntentRequest(text="标题不透明度60%，标题样式保持不变", run_id=run.id)
    )
    assert not result.can_apply


@pytest.mark.parametrize(
    "edge, expected", [("左", "left"), ("右", "right"), ("水平居中", "center")]
)
def test_explicit_frame_alignment_retains_reference_and_other_goals(edge, expected):
    text = f"请把副标题文字框与标题文字框{edge}对齐"
    requirements, controls = parse_local_requirements(text + "，副标题不透明度80%")
    alignment, opacity = controls.element_goals
    assert alignment.kind == "alignment"
    assert alignment.element_id == "subtitle" and alignment.reference_id == "title"
    assert alignment.edge == expected
    assert opacity.kind == "opacity" and opacity.element_id == "subtitle"
    assert requirements[0].quote == text
    assert controls.locks == []


@pytest.mark.parametrize(
    "text",
    [
        "标题文字框与标题文字框右对齐",
        "副标题文字框与标题文字框右对齐，副标题文字框与标题文字框左对齐",
    ],
)
def test_ambiguous_or_self_referencing_alignment_is_rejected(text):
    with pytest.raises(ValueError):
        parse_local_requirements(text)


def test_text_alignment_is_not_misrepresented_as_frame_alignment():
    _, controls = parse_local_requirements("副标题右对齐")
    assert controls.element_goals == []


async def test_alignment_preview_validates_reference_and_inherited_position_locks(tmp_path):
    from app.poster.template_loader import TemplateLoader
    from app.schemas.react import HumanCheckpoint

    runs = make_runs(tmp_path)
    runs.executor = SimpleNamespace()
    brief = PosterBrief(title="测试活动", subtitle="副标题内容")
    run = runs.create(brief)
    runs.repository.update_status(run.id, "waiting_for_human")
    layout = TemplateLoader().instantiate(brief.poster_type, brief)
    title = next(element for element in layout.elements if element.id == "title")
    subtitle = next(element for element in layout.elements if element.id == "subtitle")
    subtitle.box.x = title.box.x + 0.01
    subtitle.box.width = title.box.width
    pending = HumanCheckpoint(
        round_number=1, score=60, suggestion="检查", layout=layout.model_dump(mode="json")
    )
    request = IntentRequest(text="副标题文字框与标题文字框右对齐", run_id=run.id)

    def save():
        runs.artifacts.write_json(run.id, "pending_human.json", pending.model_dump(mode="json"))

    save()
    result = await IntentRouter(runs).resolve(request)
    assert result.can_apply and not result.fallback_used
    assert result.controls.element_goals[0].reference_id == "title"
    assert result.round_number == 1
    from app.schemas.design_control import DesignControls

    pending.controls = DesignControls(
        locks=[
            {"element_id": "title", "properties": ["position"]},
            {"element_id": "subtitle", "properties": ["position"]},
        ]
    )
    save()
    result = await IntentRouter(runs).resolve(request)
    assert not result.can_apply and any("位置锁定冲突" in item for item in result.warnings)
    # Already satisfied alignment remains valid with both positions locked.
    pending.layout["elements"] = [
        {**item, "box": {**item["box"], "x": title.box.x}} if item["id"] == "subtitle" else item
        for item in pending.layout["elements"]
    ]
    save()
    assert (await IntentRouter(runs).resolve(request)).can_apply
    # A stale reference must be caught during preview, not just tool execution.
    pending.controls = DesignControls()
    pending.layout["elements"] = [
        item for item in pending.layout["elements"] if item["id"] != "organizer"
    ]
    save()
    result = await IntentRouter(runs).resolve(request)
    result = await IntentRouter(runs).resolve(
        IntentRequest(text="副标题文字框与主办方文字框右对齐", run_id=run.id)
    )
    assert not result.can_apply and any("文字元素" in item for item in result.warnings)
