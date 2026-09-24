import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app import main
from app.core.config import Settings
from app.persistence.run_repository import RunRepository
from app.rag import lazy_chroma_store
from app.services.artifact_service import ArtifactService
from app.services.event_bus import EventBus
from app.services.run_service import RunService


def test_real_app_startup_and_local_management_do_not_call_chroma(tmp_path, monkeypatch):
    settings = Settings().model_copy(
        update={
            "data_dir": tmp_path / "data",
            "database_url": f"sqlite:///{tmp_path / 'runs.sqlite3'}",
            "langgraph_checkpoint_path": tmp_path / "graph.sqlite3",
            "deepseek_api_key": "",
            "ark_api_key": "",
            "ark_vision_model": "",
        }
    )
    calls = []

    def unavailable(**kwargs):
        calls.append(kwargs)
        raise ConnectionError("offline")

    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(lazy_chroma_store, "create_remote_chroma", unavailable)
    # Exercise production lifespan and factory; no injected demo RunService.
    with TestClient(main.create_app()) as client:
        for path in [
            "/health",
            "/datahub/users/local/profile",
            "/datahub/cases",
            "/datahub/visual-assets",
            "/datahub/harness/tools",
        ]:
            response = client.get("/api/v1" + path)
            assert response.status_code == 200, response.text
        assert client.get("/api/v1/datahub/users/local/profile").json()["preferences"] == {}
    assert calls == []
    # Windows rejects unlink while SQLAlchemy retains a pooled SQLite handle.
    (tmp_path / "runs.sqlite3").unlink()


@pytest.mark.parametrize("executor_fails", [False, True])
async def test_shutdown_releases_database_even_without_executor_or_when_close_fails(
    tmp_path, executor_fails
):
    class FailingExecutor:
        async def aclose(self):
            raise RuntimeError("checkpoint close failed")

    path = tmp_path / "runs.sqlite3"
    repository = RunRepository(f"sqlite:///{path}")
    closed = []
    event.listen(repository.database.engine, "close", lambda *args: closed.append(True))
    service = RunService(
        repository=repository,
        artifacts=ArtifactService(tmp_path / "runs"),
        event_bus=EventBus(),
        executor=FailingExecutor() if executor_fails else None,
    )
    if executor_fails:
        with pytest.raises(RuntimeError, match="checkpoint close failed"):
            await service.aclose()
    else:
        await service.aclose()
    assert closed
    path.unlink()
