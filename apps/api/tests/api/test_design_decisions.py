from pathlib import Path
from fastapi.testclient import TestClient
from app.main import create_app
from app.persistence.run_repository import RunRepository
from app.services.artifact_service import ArtifactService
from app.services.event_bus import EventBus
from app.services.run_service import RunService
from app.schemas.react import AgentExecutionOutcome, HumanCheckpoint
from app.schemas.layout_candidate import LayoutCandidate
from app.schemas.design_control import PosterAnalysis
from app.schemas.evaluation import AttentionPrediction
from tests.api.test_runs import FakeExecutor
from tests.agent.test_generation_nodes import _brief
from tests.poster.test_action_validator import make_layout


class CandidateExecutor(FakeExecutor):
    resumes = 0
    async def start(self, *args, **kwargs):
        layout = make_layout()
        moved = layout.model_copy(deep=True)
        next(item for item in moved.elements if item.role == "title").box.y = 0.35
        return AgentExecutionOutcome(status="waiting_for_human", checkpoint=HumanCheckpoint(
            round_number=0, score=70, suggestion="fixture", layout=layout.model_dump(mode="json"), analysis=PosterAnalysis(),
            layout_candidates=[LayoutCandidate(id="r0-layout-1", round_number=0, label="测试候选", poster_artifact="layout_r0_1.png", layout=moved, analysis=PosterAnalysis(), attention=AttentionPrediction(availability="unavailable"), rank_score=50)],
        ))
    async def resume(self, *args, **kwargs):
        self.resumes += 1
        return await super().resume(*args, **kwargs)


def test_candidate_lock_conflict_does_not_claim_run_or_consume_round(tmp_path: Path):
    executor = CandidateExecutor()
    service = RunService(repository=RunRepository(f"sqlite:///{tmp_path / 'runs.sqlite3'}"), artifacts=ArtifactService(tmp_path / "runs"), event_bus=EventBus(), executor=executor)
    with TestClient(create_app(run_service=service)) as client:
        created = client.post("/api/v1/runs", json=_brief().model_dump(mode="json"))
        run_id = created.json()["id"]
        base = f"/api/v1/runs/{run_id}"
        conflict = client.post(base + "/decisions", json={"action": "instruct", "expected_round_number": 0, "controls": {"selected_candidate_id": "r0-layout-1", "locks": [{"element_id": "title", "properties": ["position"]}]}})
        assert conflict.status_code == 422
        assert "锁定" in conflict.text
        assert client.get(base).json()["status"] == "waiting_for_human"
        assert client.get(base + "/pending").json()["round_number"] == 0
        stale = client.post(base + "/decisions", json={"action": "instruct", "expected_round_number": 0, "controls": {"selected_candidate_id": "r9-missing"}})
        assert stale.status_code == 422
        assert executor.resumes == 0
        finish = client.post(base + "/decisions", json={"action": "finish", "expected_round_number": 0})
        assert finish.status_code == 202
        assert executor.resumes == 1
