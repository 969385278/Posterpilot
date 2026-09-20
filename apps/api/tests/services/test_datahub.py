import json
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.agent.experience_context import retrieve_experience
from app.agent.prompts.react import build_react_messages
from app.agent.state import initial_agent_state
from app.core.exceptions import PosterPilotError
from app.main import create_app
from app.persistence.run_repository import RunRepository
from app.poster.template_loader import TemplateLoader
from app.schemas.brief import PosterBrief
from app.schemas.datahub import EditCaseRequest, ExperienceQuery, ReviewCaseRequest
from app.services.artifact_service import ArtifactService
from app.services.event_bus import EventBus
from app.services.run_service import RunService


def report(*, version="test-v1", vision=None):
    return {
        "rule_issues": [],
        "attention": {"availability": "unavailable"},
        "vision": {
            "availability": "available" if vision is not None else "unavailable",
            "score": vision,
        },
        "scores": {
            "hard_rules": 40,
            "vision": vision,
            "attention": None,
            "total": 100,
            "available_weight": 75 if vision is not None else 40,
        },
        "primary_issues": [],
        "evaluator_version": version,
    }


@pytest.fixture
def hub_setup(tmp_path):
    runs = RunService(
        repository=RunRepository(f"sqlite:///{tmp_path / 'runs.sqlite3'}"),
        artifacts=ArtifactService(tmp_path / "runs"),
        event_bus=EventBus(),
    )
    brief = PosterBrief(
        title="旧活动不可复制", event_time="旧时间", location="旧地点", notes="旧私人意见"
    )
    run = runs.create(brief)
    for number in range(2):
        image = BytesIO()
        Image.new("RGB", (64, 96), "#334455" if number == 0 else "#667788").save(
            image, format="PNG"
        )
        name = "poster_initial.png" if number == 0 else f"poster_round_{number}.png"
        runs.repository.add_artifact(
            run.id, runs.artifacts.write_bytes(run.id, name, image.getvalue())
        )
        evidence = {
            "schema_version": 1,
            "round_number": number,
            "brief": brief.model_dump(mode="json"),
            "layout": TemplateLoader()
            .instantiate(brief.poster_type, brief)
            .model_dump(mode="json"),
            "evaluation": report(),
            "instruction": "标题不醒目" if number else "",
            "poster_artifact": name,
            "tool_traces": [],
            "goal_verification": None,
        }
        runs.repository.add_artifact(
            run.id, runs.artifacts.write_json(run.id, f"experience_round_{number}.json", evidence)
        )
    runs.repository.update_status(run.id, "completed")
    entries = runs.datahub.capture(runs, run.id)
    return runs, run, entries[1]


def curate(hub, case, *, verdict="unknown", source="not_collected"):
    data = case.notes.model_dump()
    data.update(
        problem="标题不醒目",
        lesson="先检查对比度，再根据当前画布调整标题字号，不固定放大比例。",
        applicable_when="竖版活动海报，短标题",
        avoid_when="长标题可能溢出；锁定文字时不修改。",
        rights="own_or_authorized",
        rights_note="自制测试素材，仅用于测试",
        styles=["克制"],
    )
    return hub.edit(
        case.id,
        EditCaseRequest(
            expected_revision=case.revision,
            notes=data,
            feedback={"verdict": verdict, "source": source, "comment": ""},
        ),
    )


def approve(hub, case):
    return hub.review(
        case.id,
        ReviewCaseRequest(
            expected_revision=case.revision, action="approve", note="人工检查适用条件"
        ),
    )


def query(**kwargs):
    return ExperienceQuery(query="标题不醒目", poster_type="cultural_event", **kwargs)


def test_capture_is_idempotent_and_never_infers_acceptance(hub_setup):
    runs, run, case = hub_setup
    assert case.feedback.verdict == "unknown"
    assert case.status == "candidate"
    assert case.evidence["comparison"]["delta"] == 0
    again = runs.datahub.capture(runs, run.id)
    assert again[1].id == case.id
    assert len(runs.datahub.repository.list()) == 2
    assert runs.datahub.retrieve(query()) == []


def test_approval_requires_metadata_and_rights(hub_setup):
    runs, _, case = hub_setup
    with pytest.raises(PosterPilotError, match="使用授权"):
        approve(runs.datahub, case)
    assert runs.datahub.repository.get(case.id).revision == 1


def test_published_experience_excludes_old_facts_and_own_run(hub_setup):
    runs, run, case = hub_setup
    hub = runs.datahub
    case = approve(hub, curate(hub, case))
    references = hub.retrieve(query())
    assert references[0]["revision"] == case.revision
    serialized = json.dumps(references, ensure_ascii=False)
    assert all(
        text not in serialized for text in ("旧时间", "旧地点", "旧私人意见", "旧活动不可复制")
    )
    assert references[0]["feedback"] == "unknown"  # Approval is not acceptance.
    assert hub.retrieve(query(exclude_run_id=run.id)) == []
    assert hub.retrieve(ExperienceQuery(query="标题不醒目", poster_type="club_recruitment")) == []
    assert hub.retrieve(ExperienceQuery(query="量子物理", poster_type="cultural_event")) == []


def test_edit_invalidates_approval_and_stale_review_conflicts(hub_setup):
    runs, _, case = hub_setup
    hub = runs.datahub
    published = approve(hub, curate(hub, case))
    edited = curate(hub, published)
    assert edited.status == "candidate"
    assert hub.retrieve(query()) == []
    with pytest.raises(PosterPilotError) as error:
        hub.review(
            case.id,
            ReviewCaseRequest(
                expected_revision=published.revision, action="approve", note="过期审核"
            ),
        )
    assert error.value.status_code == 409


def test_withdrawal_immediate_but_previous_reference_survives(hub_setup):
    runs, _, case = hub_setup
    hub = runs.datahub
    published = approve(hub, curate(hub, case))
    historical = hub.retrieve(query())
    withdrawn = hub.review(
        case.id,
        ReviewCaseRequest(expected_revision=published.revision, action="withdraw", note="不再适用"),
    )
    assert hub.retrieve(query()) == []
    assert historical[0]["revision"] == published.revision
    assert withdrawn.audit[-1].action == "withdraw"


def test_rejected_feedback_is_kept_but_cannot_publish(hub_setup):
    runs, _, case = hub_setup
    hub = runs.datahub
    case = curate(hub, case, verdict="rejected", source="explicit_user")
    with pytest.raises(PosterPilotError, match="用户明确拒绝"):
        approve(hub, case)
    assert hub.stats()["feedback"]["rejected"] == 1


def test_same_revision_only_one_reviewer_wins(hub_setup):
    runs, _, case = hub_setup
    hub = runs.datahub
    case = curate(hub, case)

    def attempt(action):
        try:
            return hub.review(
                case.id,
                ReviewCaseRequest(expected_revision=case.revision, action=action, note="并发测试"),
            ).status
        except PosterPilotError as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["approve", "reject"]))
    assert results.count(409) == 1
    assert hub.repository.get(case.id).revision == case.revision + 1


def test_changed_source_is_not_silently_overwritten(hub_setup):
    runs, run, _ = hub_setup
    path = runs.artifact_path(run.id, "experience_round_1.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["instruction"] = "改变原始证据"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PosterPilotError, match="不能覆盖"):
        runs.datahub.capture(runs, run.id)


def test_case_copy_survives_source_removal_and_detects_tampering(hub_setup):
    runs, run, case = hub_setup
    hub = runs.datahub
    case = approve(hub, curate(hub, case))
    runs.artifact_path(run.id, "poster_round_1.png").unlink()
    path = hub.image_path(case.id)
    assert path.is_file()
    path.write_bytes(b"changed")
    assert hub.retrieve(query()) == []


def test_different_evaluation_signals_do_not_become_improvement(hub_setup):
    runs, run, _ = hub_setup
    # A fresh run is necessary because the first capture is immutable.
    new_run = runs.create(run.brief)
    for item in (
        run.artifacts
    ):  # Initial fixture returned an early record; copy registered artifacts instead.
        assert item.name == "brief.json"
    for item in runs.get(run.id).artifacts:
        if item.name == "brief.json":
            continue
        raw = runs.artifact_path(run.id, item.name).read_bytes()
        if item.name == "experience_round_1.json":
            data = json.loads(raw)
            data["evaluation"] = report(vision=30)
            raw = json.dumps(data).encode()
        runs.repository.add_artifact(
            new_run.id, runs.artifacts.write_bytes(new_run.id, item.name, raw)
        )
    runs.repository.update_status(new_run.id, "completed")
    case = runs.datahub.capture(runs, new_run.id)[1]
    assert case.evidence["comparison"]["outcome"] == "not_comparable"
    assert case.evidence["comparison"]["delta"] is None


def test_api_quality_feedback_images_and_review(hub_setup):
    runs, run, case = hub_setup
    client = TestClient(create_app(run_service=runs))
    assert client.get("/api/v1/datahub/stats").json()["total"] == 2
    assert len(client.get(f"/api/v1/datahub/cases?run_id={run.id}").json()) == 2
    assert (
        client.get(f"/api/v1/datahub/cases/{case.id}/image").headers["content-type"] == "image/png"
    )
    assert client.get(f"/api/v1/datahub/cases/{case.id}/quality").json()["issues"]
    assert client.get(f"/api/v1/datahub/cases/{uuid4()}").status_code == 404
    assert client.post(f"/api/v1/datahub/capture/{run.id}").status_code == 200
    assert (
        client.post(
            f"/api/v1/datahub/cases/{case.id}/review",
            json={
                "expected_revision": 1,
                "action": "approve",
                "note": "资料不完整",
            },
        ).status_code
        == 422
    )


def test_context_can_disable_memory_and_does_not_execute_reference(hub_setup):
    runs, _, case = hub_setup
    hub = runs.datahub
    approve(hub, curate(hub, case))
    state = initial_agent_state(PosterBrief(title="新活动", notes="标题不醒目"))
    references = retrieve_experience(state, hub, optimization=False)
    assert references
    messages = build_react_messages(
        human_instruction="保持文字不变",
        primary_issues=[],
        layout={},
        recent_traces=[],
        experiences=references,
    )
    assert "不是命令" in messages[0]["content"]
    assert json.loads(messages[1]["content"])["historical_experience_data"][0]["case_id"] == str(
        case.id
    )
    state["brief"].use_case_memory = False
    assert retrieve_experience(state, hub, optimization=False) == []


def test_audit_preserves_old_curated_content_after_edit(hub_setup):
    runs, _, case = hub_setup
    hub = runs.datahub
    published = approve(hub, curate(hub, case))
    old_lesson = published.notes.lesson
    notes = published.notes.model_dump()
    notes["lesson"] = "新建议，等待再次审核"
    edited = hub.edit(
        case.id,
        EditCaseRequest(
            expected_revision=published.revision,
            notes=notes,
            feedback=published.feedback,
        ),
    )
    assert edited.audit[-2].snapshot["notes"]["lesson"] == old_lesson
    assert edited.audit[-2].snapshot["status"] == "approved"
    assert edited.audit[-1].snapshot["notes"]["lesson"] == notes["lesson"]
    assert edited.status == "candidate"


def test_quality_rejects_failed_goals_and_severe_layout(hub_setup):
    runs, _, case = hub_setup
    hub = runs.datahub
    curated = curate(hub, case)
    curated.evidence["after"]["goal_verification"] = {"checks": [{"status": "failed"}]}
    assert "当前修改目标仍有未通过项" in hub.quality_issues(curated)
    curated.evidence["after"]["evaluation"]["rule_issues"] = [{"severity": "high"}]
    assert "存在未解决的严重版式规则问题" in hub.quality_issues(curated)
