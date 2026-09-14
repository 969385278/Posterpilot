from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app.core.exceptions import PosterPilotError
from app.persistence.run_repository import RunRepository
from app.schemas.react import AgentExecutionOutcome, HumanCheckpoint, HumanDecision
from app.services.artifact_service import ArtifactService
from app.services.event_bus import EventBus
from app.services.run_service import RunService
from tests.services.test_run_service import FakeExecutor, _brief


def test_independent_connections_only_claim_one_human_decision(tmp_path):
    url = f"sqlite:///{tmp_path / 'claims.sqlite3'}"
    first = RunRepository(url)
    second = RunRepository(url)
    record = first.create(_brief())
    first.update_status(record.id, "waiting_for_human")
    barrier = Barrier(2)

    def claim(repository):
        barrier.wait(timeout=5)
        return repository.transition_status(
            record.id, expected="waiting_for_human", status="running", current_node="human_decision"
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, [first, second]))
    assert sum(result is not None for result in results) == 1
    assert first.get(record.id).status == "running"


async def test_duplicate_start_and_decision_do_not_emit_duplicate_execution(tmp_path):
    service = RunService(
        repository=RunRepository(f"sqlite:///{tmp_path / 'runs.sqlite3'}"),
        artifacts=ArtifactService(tmp_path / "runs"),
        event_bus=EventBus(),
        executor=FakeExecutor(),
    )
    run = service.create(_brief())
    await service.execute(run.id)
    await service.execute(run.id)
    assert sum(event.type == "human_input_required" for event in service.events(run.id)) == 1
    service.begin_decision(run.id, HumanDecision(action="approve"), expected_round_number=0)
    with pytest.raises(PosterPilotError):
        service.begin_decision(run.id, HumanDecision(action="approve"), expected_round_number=0)
    assert sum(event.type == "human_input_received" for event in service.events(run.id)) == 1


class NextRoundExecutor(FakeExecutor):
    async def resume(self, run_id, decision, *, run_directory):
        return AgentExecutionOutcome(
            status="waiting_for_human",
            checkpoint=HumanCheckpoint(round_number=1, score=75, suggestion="检查新海报。"),
        )


async def test_old_page_cannot_approve_next_round(tmp_path):
    service = RunService(
        repository=RunRepository(f"sqlite:///{tmp_path / 'runs.sqlite3'}"),
        artifacts=ArtifactService(tmp_path / "runs"),
        event_bus=EventBus(),
        executor=NextRoundExecutor(),
    )
    run = service.create(_brief())
    await service.execute(run.id)
    decision = HumanDecision(action="approve")
    service.begin_decision(run.id, decision, expected_round_number=0)
    await service.resume(run.id, decision)
    with pytest.raises(PosterPilotError) as error:
        service.begin_decision(run.id, decision, expected_round_number=0)
    assert error.value.code == "stale_human_decision"
    assert service.get(run.id).status == "waiting_for_human"
    assert sum(event.type == "human_input_received" for event in service.events(run.id)) == 1
    service.begin_decision(run.id, decision, expected_round_number=1)
    assert service.get(run.id).status == "running"


async def test_transition_between_checkpoint_read_and_claim_is_rejected(tmp_path, monkeypatch):
    service = RunService(
        repository=RunRepository(f"sqlite:///{tmp_path / 'runs.sqlite3'}"),
        artifacts=ArtifactService(tmp_path / "runs"),
        event_bus=EventBus(),
        executor=NextRoundExecutor(),
    )
    run = service.create(_brief())
    await service.execute(run.id)
    original_pending = service.pending

    def racing_pending(run_id):
        checkpoint = original_pending(run_id)
        # Another worker passes through running and returns to waiting after our read.
        service.repository.update_status(run_id, "running")
        service.repository.update_status(run_id, "waiting_for_human")
        return checkpoint

    monkeypatch.setattr(service, "pending", racing_pending)
    with pytest.raises(PosterPilotError):
        service.begin_decision(run.id, HumanDecision(action="approve"), expected_round_number=0)
    assert not any(event.type == "human_input_received" for event in service.events(run.id))


async def test_missing_executor_does_not_claim_waiting_task(tmp_path):
    service = RunService(
        repository=RunRepository(f"sqlite:///{tmp_path / 'runs.sqlite3'}"),
        artifacts=ArtifactService(tmp_path / "runs"),
        event_bus=EventBus(),
        executor=FakeExecutor(),
    )
    run = service.create(_brief())
    await service.execute(run.id)
    service.executor = None
    with pytest.raises(PosterPilotError) as error:
        service.begin_decision(run.id, HumanDecision(action="approve"), expected_round_number=0)
    assert error.value.status_code == 503
    assert service.get(run.id).status == "waiting_for_human"
