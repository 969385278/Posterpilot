import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.schemas.run import RunEvent
from app.services.artifact_service import ArtifactService


def test_artifact_service_writes_json_inside_run_directory(tmp_path: Path) -> None:
    service = ArtifactService(tmp_path)
    run_id = uuid4()

    reference = service.write_json(run_id, "brief.json", {"title": "红楼梦研讨分享会"})
    artifact_path = tmp_path / str(run_id) / "brief.json"

    assert artifact_path.exists()
    assert json.loads(artifact_path.read_text(encoding="utf-8"))["title"] == "红楼梦研讨分享会"
    assert reference.relative_path == f"{run_id}/brief.json"
    assert reference.media_type == "application/json"


def test_artifact_service_appends_structured_events(tmp_path: Path) -> None:
    service = ArtifactService(tmp_path)
    run_id = uuid4()
    event = RunEvent(
        run_id=run_id,
        type="run_created",
        message="任务已创建",
    )

    service.append_event(event)
    service.append_event(event.model_copy(update={"type": "node_started", "node": "parse_brief"}))

    lines = (tmp_path / str(run_id) / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["node"] == "parse_brief"


@pytest.mark.parametrize("name", ["../secret.json", "nested/result.json", "..\\secret.json"])
def test_artifact_service_rejects_path_traversal(tmp_path: Path, name: str) -> None:
    service = ArtifactService(tmp_path)

    with pytest.raises(ValueError, match="artifact name"):
        service.write_json(uuid4(), name, {"unsafe": True})

