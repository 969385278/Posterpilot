from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence.run_repository import RunRepository
from app.schemas.brief import PosterBrief
from app.schemas.react import AgentExecutionOutcome, HumanCheckpoint
from app.services.artifact_service import ArtifactService
from app.services.event_bus import EventBus
from app.services.run_service import RunService


async def test_sse_subscribes_before_replay_deduplicates_and_honors_cursor(tmp_path, monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from starlette.requests import Request

    from app.api.routes.runs import stream_events
    from tests.services.test_user_memory import make_runs

    service = make_runs(tmp_path)
    run = service.create(PosterBrief(title="实时事件"))
    service.repository.update_status(run.id, "running")
    original = service.events
    first = original(run.id)[0]

    def history_with_concurrent_event(run_id):
        history = original(run_id)
        # Simulate events happening exactly between history capture and live reads.
        service.event_bus.publish_nowait(first)
        service._emit(run_id, "node_completed", "实时设计完成", node="plan_design")
        service.repository.update_status(run_id, "completed")
        service._emit(run_id, "run_completed", "实时任务完成")
        return history

    monkeypatch.setattr(service, "events", history_with_concurrent_event)
    request = Request(
        {
            "type": "http",
            "headers": [],
            "app": SimpleNamespace(state=SimpleNamespace(run_service=service)),
        }
    )
    response = await stream_events(run.id, request)

    async def consume(iterator):
        return "".join([part async for part in iterator])

    output = await asyncio.wait_for(consume(response.body_iterator), timeout=2)
    assert output.count("event: run_created") == 1
    assert output.count("event: node_completed") == 1
    assert output.count("event: run_completed") == 1
    assert "event: stream_end" in output
    assert not service.event_bus._subscribers

    monkeypatch.setattr(service, "events", original)
    request = Request(
        {
            "type": "http",
            "headers": [(b"last-event-id", str(first.id).encode())],
            "app": SimpleNamespace(state=SimpleNamespace(run_service=service)),
        }
    )
    response = await stream_events(run.id, request)
    output = await consume(response.body_iterator)
    assert "event: run_created" not in output
    assert "event: node_completed" in output
    assert "event: stream_end" in output


def test_old_event_logs_get_stable_ids_without_rewriting_and_unknown_run_is_404(tmp_path):
    import json
    from uuid import uuid4

    from tests.services.test_user_memory import make_runs

    service = make_runs(tmp_path)
    run = service.create(PosterBrief(title="旧事件"))
    path = service.artifacts.run_directory(run.id) / "events.jsonl"
    record = json.loads(path.read_text("utf-8").splitlines()[0])
    record.pop("id")
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    before = path.read_bytes()
    assert service.events(run.id)[0].id == service.events(run.id)[0].id
    assert path.read_bytes() == before
    client = TestClient(create_app(run_service=service))
    assert client.get(f"/api/v1/runs/{uuid4()}/events").status_code == 404


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
