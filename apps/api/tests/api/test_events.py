from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence.run_repository import RunRepository
from app.schemas.brief import PosterBrief
from app.schemas.react import AgentExecutionOutcome, HumanCheckpoint
from app.services.artifact_service import ArtifactService
from app.services.event_bus import EventBus
from app.services.run_service import RunService


class FakeExecutor:
    async def start(self, brief: PosterBrief, *, run_id, run_directory: Path):
        return AgentExecutionOutcome(
            status="waiting_for_human",
            checkpoint=HumanCheckpoint(
                round_number=0,
                score=70,
                primary_issues=["标题层级不足"],
                suggestion="增强标题。",
            ),
        )


def test_events_endpoint_replays_persisted_run_events(tmp_path: Path) -> None:
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

    run_id = client.post("/api/v1/runs", json=payload).json()["id"]
    response = client.get(f"/api/v1/runs/{run_id}/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: run_created" in response.text
    assert "event: human_input_required" in response.text
