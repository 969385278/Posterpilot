"""Exercise the graph, renderer, review API and cross-run references without paid APIs."""

import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

from app.datahub_demo import create_app


def test_offline_data_loop_end_to_end(tmp_path):
    script = Path(__file__).resolve().parents[4] / "scripts" / "verify_datahub.py"
    spec = importlib.util.spec_from_file_location("verify_datahub", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.verify(tmp_path / "hub")
    assert all(result["checks"].values())
    assert result["reference_counts"] == {"disabled": 0, "enabled": 1}
    assert result["paid_model_calls"] == 0
    assert not result["quality_improvement_claim"]


def test_capture_failure_does_not_fail_poster_and_manual_retry_recovers(tmp_path, monkeypatch):
    app = create_app(tmp_path / "hub")
    with TestClient(app) as client:
        hub = app.state.run_service.datahub
        capture = hub.capture

        def unavailable(*args, **kwargs):
            raise OSError("temporary datahub failure")

        monkeypatch.setattr(hub, "capture", unavailable)
        response = client.post("/api/v1/runs", json={"title": "数据回流失败仍生成海报"})
        assert response.status_code == 202
        run_id = response.json()["id"]
        run = client.get(f"/api/v1/runs/{run_id}").json()
        assert run["status"] == "waiting_for_human"
        assert client.get(f"/api/v1/runs/{run_id}/pending").status_code == 200
        assert hub.repository.list() == []
        monkeypatch.setattr(hub, "capture", capture)
        recovered = client.post(f"/api/v1/datahub/capture/{run_id}")
        assert recovered.status_code == 200
        assert len(recovered.json()) == 1
        assert recovered.json()[0]["status"] == "candidate"
