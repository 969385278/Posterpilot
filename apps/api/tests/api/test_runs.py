from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence.run_repository import RunRepository
from app.schemas.brief import PosterBrief
from app.schemas.react import AgentExecutionOutcome, HumanCheckpoint, HumanDecision
from app.services.artifact_service import ArtifactService
from app.services.event_bus import EventBus
from app.services.run_service import RunService


class FakeExecutor:
    async def start(
        self,
        brief: PosterBrief,
        *,
        run_id,
        run_directory: Path,
    ) -> AgentExecutionOutcome:
        return AgentExecutionOutcome(
            status="waiting_for_human",
            checkpoint=HumanCheckpoint(
                round_number=0,
                score=70,
                primary_issues=["标题层级不足"],
                suggestion="增强标题。",
            ),
        )

    async def resume(
        self,
        run_id,
        decision: HumanDecision,
        *,
        run_directory: Path,
    ) -> AgentExecutionOutcome:
        return AgentExecutionOutcome(
            status="completed",
            result={"outcome": "unchanged", "title": "红楼梦研讨分享会", "rounds": []},
        )


def test_create_list_and_read_run_artifacts(tmp_path: Path) -> None:
    service = RunService(
        repository=RunRepository(f"sqlite:///{tmp_path / 'runs.sqlite3'}"),
        artifacts=ArtifactService(tmp_path / "runs"),
        event_bus=EventBus(),
        executor=FakeExecutor(),
    )
    client = TestClient(create_app(run_service=service))
    payload = {
        "poster_type": "cultural_event",
        "topic": "红楼梦研讨分享会",
        "target_audience": "大学生",
        "title": "红楼梦研讨分享会",
        "event_time": "2026年7月20日 19:00",
        "location": "图书馆报告厅",
        "organizer": "文学社",
    }

    created = client.post("/api/v1/runs", json=payload)
    run_id = created.json()["id"]
    listed = client.get("/api/v1/runs")
    waiting = client.get(f"/api/v1/runs/{run_id}")
    pending = client.get(f"/api/v1/runs/{run_id}/pending")
    missing_version = client.post(f"/api/v1/runs/{run_id}/decisions", json={"action": "finish"})
    stale = client.post(
        f"/api/v1/runs/{run_id}/decisions", json={"action": "finish", "expected_round_number": 1}
    )
    decision = client.post(
        f"/api/v1/runs/{run_id}/decisions", json={"action": "finish", "expected_round_number": 0}
    )
    result = client.get(f"/api/v1/runs/{run_id}")
    artifact = client.get(f"/api/v1/runs/{run_id}/artifacts/result.json")

    assert created.status_code == 202
    assert listed.status_code == 200
    assert waiting.json()["status"] == "waiting_for_human"
    assert pending.json()["primary_issues"] == ["标题层级不足"]
    assert missing_version.status_code == 422
    assert stale.status_code == 409
    assert decision.status_code == 202
    assert result.json()["status"] == "completed"
    assert artifact.json()["outcome"] == "unchanged"


def test_decision_is_rejected_when_run_is_not_waiting(tmp_path: Path) -> None:
    service = RunService(
        repository=RunRepository(f"sqlite:///{tmp_path / 'runs.sqlite3'}"),
        artifacts=ArtifactService(tmp_path / "runs"),
        event_bus=EventBus(),
        executor=FakeExecutor(),
    )
    client = TestClient(create_app(run_service=service))
    created = client.post(
        "/api/v1/runs",
        json={
            "poster_type": "cultural_event",
            "topic": "红楼梦研讨分享会",
            "target_audience": "大学生",
            "title": "红楼梦研讨分享会",
            "event_time": "2026年7月20日 19:00",
            "location": "图书馆报告厅",
            "organizer": "文学社",
        },
    )
    run_id = created.json()["id"]
    client.post(
        f"/api/v1/runs/{run_id}/decisions", json={"action": "finish", "expected_round_number": 0}
    )

    repeated = client.post(
        f"/api/v1/runs/{run_id}/decisions", json={"action": "finish", "expected_round_number": 0}
    )

    assert repeated.status_code == 409
