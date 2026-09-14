from fastapi.testclient import TestClient
from io import BytesIO

from PIL import Image

from app.demo import create_demo_app
from tests.services.test_run_service import _brief


def test_offline_demo_uses_real_graph_and_restores_after_app_recreation(tmp_path):
    with TestClient(create_demo_app(tmp_path)) as client:
        run_id = client.post("/api/v1/runs", json=_brief().model_dump(mode="json")).json()["id"]
        assert client.get(f"/api/v1/runs/{run_id}/pending").json()["round_number"] == 0
    with TestClient(create_demo_app(tmp_path)) as client:
        response = client.post(
            f"/api/v1/runs/{run_id}/decisions",
            json={"action": "approve", "expected_round_number": 0},
        )
        assert response.status_code == 202
        pending = client.get(f"/api/v1/runs/{run_id}/pending").json()
        assert pending["round_number"] == 1
        assert any("40/100" in note for note in pending["evaluation_notes"])
        assert any("视觉评测不可用" in note for note in pending["evaluation_notes"])
        assert [trace["tool_name"] for trace in pending["tool_traces"]] == [
            "search_design_knowledge",
            "modify_typography",
        ]
        assert all(trace["success"] for trace in pending["tool_traces"])
        client.post(
            f"/api/v1/runs/{run_id}/decisions",
            json={"action": "finish", "expected_round_number": 1},
        )
        assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "completed"
        image = client.get(f"/api/v1/runs/{run_id}/artifacts/poster_round_1.png")
        assert image.content.startswith(b"\x89PNG")


def test_offline_demo_failure_is_visible_to_the_frontend(tmp_path):
    with TestClient(create_demo_app(tmp_path, fail_image=True)) as client:
        run_id = client.post("/api/v1/runs", json=_brief().model_dump(mode="json")).json()["id"]
        failed = client.get(f"/api/v1/runs/{run_id}").json()
        assert failed["status"] == "failed"
        assert "主动注入生图失败" in failed["error_message"]


def test_synthetic_attention_artifacts_survive_round_and_app_recreation(tmp_path):
    with TestClient(create_demo_app(tmp_path, synthetic_attention=True)) as client:
        run_id = client.post("/api/v1/runs", json=_brief().model_dump(mode="json")).json()["id"]
        pending = client.get(f"/api/v1/runs/{run_id}/pending").json()
        assert pending["attention_artifact"] == "attention_initial.png"
        assert any("65/100" in note for note in pending["evaluation_notes"])
        image = client.get(f"/api/v1/runs/{run_id}/artifacts/attention_initial.png")
        assert image.status_code == 200
        assert Image.open(BytesIO(image.content)).size == (384, 512)
    with TestClient(create_demo_app(tmp_path, synthetic_attention=True)) as client:
        response = client.post(
            f"/api/v1/runs/{run_id}/decisions",
            json={"action": "approve", "expected_round_number": 0},
        )
        assert response.status_code == 202
        pending = client.get(f"/api/v1/runs/{run_id}/pending").json()
        assert pending["attention_artifact"] == "attention_round_1.png"
        assert pending["initial_attention_artifact"] == "attention_initial.png"
        assert pending["rounds"][0]["evaluation"]["attention"]["model"] == (
            "offline-demo-synthetic-attention"
        )
        assert client.get(f"/api/v1/runs/{run_id}/artifacts/attention_initial.png").status_code == 200
        assert client.get(f"/api/v1/runs/{run_id}/artifacts/attention_round_1.png").status_code == 200
