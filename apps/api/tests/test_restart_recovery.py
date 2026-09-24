import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app import main
from app.core.config import Settings
from app.persistence.run_repository import RunRepository
from app.persistence.runtime_ownership import runtime_ownership
from app.schemas.brief import PosterBrief


def configuration(tmp_path):
    return Settings().model_copy(
        update={
            "data_dir": tmp_path / "data",
            "database_url": f"sqlite:///{tmp_path / 'runs.sqlite3'}",
            "langgraph_checkpoint_path": tmp_path / "graph.sqlite3",
        }
    )


def test_exclusive_startup_reconciles_active_tasks_but_preserves_paused_and_final(
    tmp_path, monkeypatch
):
    settings = configuration(tmp_path)
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    repo = RunRepository(settings.database_url)
    records = {}
    for status in ["queued", "running", "waiting_for_human", "completed", "failed"]:
        record = repo.create(PosterBrief(title=status))
        records[status] = repo.update_status(record.id, status, current_node="original")
    repo.database.close()
    paused = settings.data_dir / "runs" / str(records["waiting_for_human"].id)
    paused.mkdir(parents=True)
    checkpoint = paused / "pending_human.json"
    checkpoint.write_bytes(b'{"preserve": "original-checkpoint"}')
    artifact = settings.data_dir / "runs" / str(records["running"].id) / "poster_initial.png"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"existing-render")
    with TestClient(main.create_app()) as client:
        for status, old in records.items():
            current = client.get(f"/api/v1/runs/{old.id}").json()
            if status in {"queued", "running"}:
                assert current["status"] == "failed"
                assert current["error_code"] == "execution_interrupted"
            else:
                assert current["status"] == status
                assert current["current_node"] == "original"
        assert checkpoint.read_bytes() == b'{"preserve": "original-checkpoint"}'
        assert artifact.read_bytes() == b"existing-render"
        events = client.app.state.run_service.events(records["running"].id)
        assert sum(e.node == "startup_recovery" for e in events) == 1
        # A competing server must not misclassify the active owner's work.
        live = client.app.state.run_service.create(PosterBrief(title="still alive"))
        with pytest.raises(RuntimeError, match="API 实例"), TestClient(main.create_app()):
            pass
        assert client.app.state.run_service.get(live.id).status == "queued"
    with TestClient(main.create_app()) as client:
        assert client.app.state.run_service.get(live.id).error_code == "execution_interrupted"
        assert len(client.app.state.run_service.events(records["running"].id)) == len(events)


def test_lock_released_after_failed_initialization(tmp_path, monkeypatch):
    settings = configuration(tmp_path)
    monkeypatch.setattr(main, "get_settings", lambda: settings)

    def fail(settings):
        raise ValueError("factory failed")

    monkeypatch.setattr(main, "_build_run_service", fail)
    with pytest.raises(ValueError, match="factory failed"), TestClient(main.create_app()):
        pass
    with runtime_ownership(settings.database_url) as exclusive:
        assert exclusive


def test_abandoned_records_are_not_limited_to_history_page(tmp_path):
    repo = RunRepository(f"sqlite:///{tmp_path / 'many.sqlite3'}")
    try:
        for _ in range(205):
            repo.create(PosterBrief(title="queued"))
        recovered = repo.interrupt_abandoned_runs()
        assert len(recovered) == 205
        assert all(record.error_code == "execution_interrupted" for record in recovered)
        assert repo.interrupt_abandoned_runs() == []
    finally:
        repo.database.close()


@pytest.mark.parametrize("url", ["sqlite:///:memory:", "postgresql://localhost/test"])
def test_nonlocal_databases_are_not_automatically_reconciled(url):
    with runtime_ownership(url) as exclusive:
        assert not exclusive


def test_os_releases_ownership_after_process_exits_without_cleanup(tmp_path):
    database = tmp_path / "crashed.sqlite3"
    script = (
        "import os,sys; from filelock import FileLock; "
        "lock=FileLock(sys.argv[1], timeout=0); lock.acquire(); os._exit(0)"
    )
    subprocess.run(
        [sys.executable, "-c", script, str(database) + ".runtime.lock"],
        check=True,
        timeout=15,
        capture_output=True,
    )
    with runtime_ownership(f"sqlite:///{database}") as exclusive:
        assert exclusive
