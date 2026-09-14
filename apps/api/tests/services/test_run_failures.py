import pytest

from app.persistence.run_repository import RunRepository
from app.schemas.react import HumanDecision
from app.services.artifact_service import ArtifactService
from app.services.event_bus import EventBus
from app.services.run_service import RunService
from tests.services.test_run_service import FakeExecutor, _brief


@pytest.fixture
def service(tmp_path):
    return RunService(
        repository=RunRepository(f"sqlite:///{tmp_path / 'runs.sqlite3'}"),
        artifacts=ArtifactService(tmp_path / "runs"),
        event_bus=EventBus(),
        executor=FakeExecutor(),
    )


@pytest.mark.parametrize("phase", ["start", "resume"])
async def test_result_file_failure_does_not_leave_task_running(service, monkeypatch, phase):
    run = service.create(_brief())
    if phase == "resume":
        await service.execute(run.id)
        service.begin_decision(run.id, HumanDecision(action="approve"), expected_round_number=0)

    def fail_write(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(service.artifacts, "write_json", fail_write)
    outcome = (
        await service.execute(run.id)
        if phase == "start"
        else await service.resume(run.id, HumanDecision(action="approve"))
    )
    assert outcome.status == "failed"
    assert service.get(run.id).status == "failed"
    assert outcome.error_message == "disk full"
    assert any(event.type == "run_failed" for event in service.events(run.id))


async def test_artifact_registration_failure_is_recorded(service, monkeypatch):
    run = service.create(_brief())

    def fail_register(*args, **kwargs):
        raise RuntimeError("artifact index unavailable")

    monkeypatch.setattr(service.repository, "add_artifact", fail_register)
    outcome = await service.execute(run.id)
    assert outcome.status == "failed"
    assert outcome.error_message == "artifact index unavailable"


async def test_event_file_failure_does_not_block_execution_or_human_resume(
    service, monkeypatch, caplog
):
    run = service.create(_brief())
    queue = service.event_bus.subscribe(run.id)

    def fail_event(*args, **kwargs):
        raise OSError("trace directory unavailable")

    monkeypatch.setattr(service.artifacts, "append_event", fail_event)
    assert (await service.execute(run.id)).status == "waiting_for_human"
    assert service.pending(run.id).round_number == 0
    service.begin_decision(run.id, HumanDecision(action="approve"), expected_round_number=0)
    assert (await service.resume(run.id, HumanDecision(action="approve"))).status == "completed"
    assert service.artifact_path(run.id, "result.json").is_file()
    assert "Could not persist event" in caplog.text
    published = []
    while not queue.empty():
        published.append(queue.get_nowait().type)
    assert "human_input_received" in published
    assert "run_completed" in published
    service.event_bus.unsubscribe(run.id, queue)


async def test_event_bus_failure_keeps_committed_task_state(service, monkeypatch, caplog):
    run = service.create(_brief())

    def fail_publish(*args, **kwargs):
        raise RuntimeError("subscriber failure")

    monkeypatch.setattr(service.event_bus, "publish_nowait", fail_publish)
    assert (await service.execute(run.id)).status == "waiting_for_human"
    assert any(event.type == "human_input_required" for event in service.events(run.id))
    assert "Could not publish event" in caplog.text


async def test_persistent_database_failure_is_not_reported_as_saved_failure(service, monkeypatch):
    run = service.create(_brief())

    def fail_status(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(service.repository, "update_status", fail_status)
    with pytest.raises(RuntimeError, match="database unavailable"):
        await service.execute(run.id)
    # The agent completed, but no business transition could be saved. No false
    # success/failure return, and no terminal event claiming a durable state.
    assert service.get(run.id).status == "running"
    assert not any(
        event.type in {"run_failed", "human_input_required", "run_completed"}
        for event in service.events(run.id)
    )
