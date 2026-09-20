import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.paths import PROJECT_ROOT
from app.rag.case_repository import CaseRepository
from app.schemas.brief import PosterBrief
from app.showcase import create_app, reviewed_media


def test_reviewed_assets_and_public_outputs_are_traceable():
    media = reviewed_media()  # Verifies original bytes against source hashes and rights.
    assert set(media) == {"nebula", "irises", "tetons"}
    assert all(asset["creator"] and asset["source_url"] for asset in media.values())
    report = json.loads(
        (PROJECT_ROOT / "apps/web/public/showcase/index.json").read_text(encoding="utf-8")
    )
    assert report["paid_model_calls"] == 0
    assert report["real_user_feedback"] is False
    assert report["quality_improvement_claim"] is False
    assert report == json.loads(
        (PROJECT_ROOT / "apps/web/src/data/showcase.json").read_text(encoding="utf-8")
    )
    for entry in report["entries"]:
        PosterBrief.model_validate(entry["brief"])
        assert entry["source"]["sha256"] == media[entry["id"]]["sha256"]
        for version, url in entry["images"].items():
            path = PROJECT_ROOT / "apps/web/public" / url.lstrip("/")
            assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["image_hashes"][version]
            with Image.open(path) as image:
                assert image.size == (1080, 1440)
        assert entry["image_hashes"]["initial"] != entry["image_hashes"]["optimized"]
        assert entry["visual_review"]["image_sha256"] == entry["image_hashes"]["optimized"]
        if entry["quality_issues"]:
            assert entry["case_status"] != "approved"
            assert entry["visual_review"]["decision"] == "hold"


def test_rejected_external_candidates_are_not_in_the_case_catalog():
    cases = CaseRepository().list_cases()
    ids = {case.id for case in cases}
    assert len(ids) == 15
    assert len({case.source.image_sha256 for case in cases}) == len(cases)
    for rejected in ("commons-151025018", "commons-31973814", "commons-106991594"):
        assert rejected not in ids


@pytest.mark.parametrize("scenario_id", ["nebula", "irises", "tetons"])
def test_real_sourced_retrieval_can_resume_and_capture_without_paid_models(tmp_path, scenario_id):
    scenarios = json.loads(
        (PROJECT_ROOT / "data/showcase/scenarios.json").read_text(encoding="utf-8")
    )
    brief = next(item["brief"] for item in scenarios if item["id"] == scenario_id)
    with TestClient(create_app(tmp_path)) as client:
        response = client.post("/api/v1/runs", json=brief)
        assert response.status_code == 202
        run_id = response.json()["id"]
        assert client.get(f"/api/v1/runs/{run_id}/pending").json()["round_number"] == 0
        response = client.post(
            f"/api/v1/runs/{run_id}/decisions",
            json={
                "action": "instruct",
                "expected_round_number": 0,
                "instruction": "把时间地点放大，保留其他内容。",
            },
        )
        assert response.status_code == 202
        assert client.get(f"/api/v1/runs/{run_id}/pending").json()["round_number"] == 1
        cases = client.get(f"/api/v1/datahub/cases?run_id={run_id}").json()
        assert len(cases) == 2
        for case in cases:
            assert case["origin"] == "offline_demo"
            assert case["feedback"]["verdict"] == "unknown"
            assert case["feedback"]["source"] == "not_collected"
            assert case["status"] == "candidate"
        evidence = cases[-1]["evidence"]
        assert evidence["after"]["brief"]["title"] == brief["title"]
        title = next(
            fact
            for fact in evidence["after"]["analysis"]["text_facts"]
            if fact["element_id"] == "title"
        )
        expected_font = {
            "nebula": "ZCOOL QingKe HuangYou Regular",
            "irises": "Ma Shan Zheng Regular",
            "tetons": "Long Cang Regular",
        }
        assert title["font_name"] == expected_font[scenario_id]
        assert title["fits_box"] is True
