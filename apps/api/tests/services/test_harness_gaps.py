"""Failure aggregation policy tests, with real SQLite and explicit source fixtures."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import PosterPilotError
from app.schemas.brief import PosterBrief
from app.schemas.tool_release import GapTriageRequest
from app.services.tool_harness import ToolHarness
from tests.services.test_user_memory import make_runs


def source(*, origin="offline_demo", checks=None, traces=None, verdict="pending"):
    return SimpleNamespace(
        id=uuid4(),
        run_id=uuid4(),
        revision=1,
        evidence_hash="fixed-evidence",
        origin=origin,
        status="approved",
        feedback=SimpleNamespace(verdict=verdict, comment="标题仍然难读"),
        evidence={
            "after": {
                "goal_verification": {"outcome": "met", "checks": checks or []},
                "tool_traces": traces or [],
            }
        },
    )


@pytest.fixture
def setup(tmp_path):
    cases = {}

    def get(case_id):
        if case_id not in cases:
            raise PosterPilotError("missing", code="missing", status_code=404)
        return cases[case_id]

    hub = SimpleNamespace(
        repository=SimpleNamespace(list=lambda: list(cases.values()), get=get),
        quality_issues=lambda case: [],
    )
    return ToolHarness(tmp_path / "harness", hub), cases


def triage(gap, resolution=None):
    return GapTriageRequest(
        expected_revision=gap["revision"],
        category="capability_gap",
        note="逐项核对验收证据",
        resolution_case_id=resolution,
    )


def test_collection_deduplicates_concurrent_scans_and_editorial_revisions(setup):
    harness, cases = setup
    case = source(verdict="rejected", checks=[{"key": "contrast", "status": "failed"}])
    cases[case.id] = case
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: harness.collect(), range(4)))
    assert sum(item["new_observations"] for item in results) == 2
    case.revision += 1
    assert harness.collect()["new_observations"] == 0
    assert all(gap["occurrences"] == 1 for gap in harness.gaps())
    case.feedback.comment = "修改后仍然不满意"
    assert harness.collect()["new_observations"] == 1


def test_resolution_requires_matching_passed_evidence_and_invalidates_on_source_change(setup):
    harness, cases = setup
    failed = source(checks=[{"key": "contrast", "status": "failed"}])
    cases[failed.id] = failed
    gap = harness.collect()["gaps"][0]
    resolved = source(checks=[{"key": "contrast", "status": "passed"}])
    cases[resolved.id] = resolved
    resolved.origin = "runtime"
    with pytest.raises(PosterPilotError) as error:
        harness.triage(gap["id"], triage(gap, resolved.id))
    assert error.value.code == "resolution_origin_mismatch"
    resolved.origin = failed.origin
    resolved.evidence["after"]["goal_verification"]["checks"][0]["key"] = "unrelated"
    with pytest.raises(PosterPilotError) as error:
        harness.triage(gap["id"], triage(gap, resolved.id))
    assert error.value.code == "resolution_not_matched"
    resolved.evidence["after"]["goal_verification"]["checks"][0]["key"] = "contrast"
    harness.triage(gap["id"], triage(gap, resolved.id))
    assert harness.gaps()[0]["status"] == "resolved"
    with pytest.raises(PosterPilotError) as error:
        harness.triage(gap["id"], triage(gap))
    assert error.value.code == "stale_gap"
    resolved.revision += 1
    assert harness.gaps()[0]["status"] == "resolution_stale"
    del cases[resolved.id]
    assert harness.gaps()[0]["status"] == "resolution_stale"
    other = source(checks=[{"key": "contrast", "status": "failed"}])
    cases[other.id] = other
    assert harness.collect()["new_observations"] == 1
    reopened = harness.gaps()[0]
    assert reopened["status"] == "open" and reopened["occurrences"] == 2
    assert reopened["audit"][0]["resolution_case_id"] == str(resolved.id)


def test_failure_before_case_creation_is_captured_without_masking_original_error(
    tmp_path, monkeypatch
):
    runs = make_runs(tmp_path)
    record = runs.create(PosterBrief(title="失败运行"))
    failed = runs._fail_execution(
        record.id, RuntimeError("provider timeout 30"), node="generate", code="provider_failed"
    )
    assert failed.status == "failed"
    gap = runs.harness.gaps()[0]
    assert gap["observations"][0]["case_id"] is None
    assert gap["observations"][0]["brief"]["title"] == "失败运行"
    assert not runs.harness.record_run_failure(failed, origin=runs.data_origin)

    def unavailable(*args, **kwargs):
        raise RuntimeError("harness unavailable")

    monkeypatch.setattr(runs.harness, "record_run_failure", unavailable)
    assert (
        runs._fail_execution(
            record.id,
            RuntimeError("original provider error"),
            node="generate",
            code="provider_failed",
        ).error_message
        == "original provider error"
    )


def test_failed_run_resolution_requires_original_brief(setup):
    harness, cases = setup
    run = SimpleNamespace(
        id=uuid4(),
        status="failed",
        error_message="timeout",
        error_code="provider_failed",
        brief=PosterBrief(title="原始需求"),
    )
    harness.record_run_failure(run, origin="offline_demo")
    gap = harness.gaps()[0]
    resolved = source()
    cases[resolved.id] = resolved
    resolved.evidence["after"]["brief"] = PosterBrief(title="其他需求").model_dump(mode="json")
    with pytest.raises(PosterPilotError) as error:
        harness.triage(gap["id"], triage(gap, resolved.id))
    assert error.value.code == "resolution_not_matched"
    resolved.evidence["after"]["brief"] = run.brief.model_dump(mode="json")
    assert harness.triage(gap["id"], triage(gap, resolved.id))["status"] == "resolved"


def test_grouped_run_failures_require_full_coverage_and_track_each_source(setup):
    harness, cases = setup
    resolutions = []
    for title in ["标题强调", "活动信息", "标题强调"]:
        run = SimpleNamespace(
            id=uuid4(), status="failed", error_message="timeout",
            error_code="provider_failed", brief=PosterBrief(title=title),
        )
        harness.record_run_failure(run, origin="offline_demo")
        if len(resolutions) < 2:
            resolved = source()
            resolved.evidence["after"]["brief"] = run.brief.model_dump(mode="json")
            cases[resolved.id] = resolved
            resolutions.append(resolved)
    gap = harness.gaps()[0]
    assert gap["occurrences"] == 3
    with pytest.raises(PosterPilotError) as error:
        harness.triage(gap["id"], triage(gap, resolutions[0].id))
    assert error.value.code == "resolution_incomplete"
    assert harness.gaps()[0]["revision"] == gap["revision"]
    request = triage(gap).model_copy(update={
        "resolution_case_ids": [item.id for item in resolutions],
    })
    result = harness.triage(gap["id"], request)
    assert result["status"] == "resolved"
    coverage = result["audit"][-1]["observation_coverage"]
    assert sorted(len(ids) for ids in coverage.values()) == [1, 2]
    assert harness.gaps()[0]["status"] == "resolved"
    resolutions[1].revision += 1
    assert harness.gaps()[0]["status"] == "resolution_stale"


def test_old_partial_resolution_is_no_longer_reported_as_resolved(setup):
    import json

    harness, cases = setup
    for title in ["需求一", "需求二"]:
        harness.record_run_failure(SimpleNamespace(
            id=uuid4(), status="failed", error_message="timeout",
            error_code="provider_failed", brief=PosterBrief(title=title),
        ), origin="offline_demo")
    resolved = source()
    resolved.evidence["after"]["brief"] = PosterBrief(title="需求一").model_dump(mode="json")
    cases[resolved.id] = resolved
    gap = harness.gaps()[0]
    gap.pop("observations")
    gap.update(status="resolved", audit=[{
        "resolution_case_id": str(resolved.id), "resolution_revision": resolved.revision,
    }])
    with harness.connect(write=True) as db:
        db.execute("UPDATE capability_gaps SET payload=? WHERE id=?", (json.dumps(gap), gap["id"]))
    assert harness.gaps()[0]["status"] == "resolution_stale"


def test_duplicate_resolution_sources_are_rejected():
    from pydantic import ValidationError

    source_id = uuid4()
    with pytest.raises(ValidationError, match="must be unique"):
        GapTriageRequest(
            expected_revision=1, category="infrastructure", note="测试",
            resolution_case_id=source_id, resolution_case_ids=[source_id],
        )


def test_manual_collection_backfills_all_failed_runs_beyond_history_limit(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app

    runs = make_runs(tmp_path)
    expected_ids = set()
    for index in range(205):
        record = runs.repository.create(PosterBrief(title=f"历史失败 {index}"))
        runs.repository.update_status(
            record.id, "failed", error_code="old_failure", error_message="模型调用失败"
        )
        expected_ids.add(str(record.id))
    runs.repository.create(PosterBrief(title="仍在排队，不应归集失败"))
    assert runs.harness.gaps() == []
    client = TestClient(create_app(runs))
    response = client.post("/api/v1/datahub/harness/collect")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["failed_runs_scanned"] == 205
    assert result["new_run_observations"] == 205
    assert result["gaps"][0]["occurrences"] == 205
    assert {item["run_id"] for item in result["gaps"][0]["observations"]} == expected_ids
    assert client.post("/api/v1/datahub/harness/collect").json()["new_observations"] == 0
