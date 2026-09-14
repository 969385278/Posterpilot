from pathlib import Path

from app.persistence.run_repository import RunRepository
from app.schemas.brief import PosterBrief
from app.schemas.react import AgentExecutionOutcome, HumanCheckpoint, HumanDecision
from app.services.artifact_service import ArtifactService
from app.services.event_bus import EventBus
from app.services.run_service import RunService


class FakeExecutor:
    async def start(
        self,
        brief: PosterBrief,
        *,
        run_id,
        run_directory: Path,
    ) -> AgentExecutionOutcome:
        assert run_directory.is_dir()
        (run_directory / "poster_initial.png").write_bytes(b"placeholder")
        return AgentExecutionOutcome(
            status="waiting_for_human",
            checkpoint=HumanCheckpoint(
                round_number=0,
                score=72,
                primary_issues=["标题层级不足"],
                suggestion="优先增强标题。",
            ),
        )

    async def resume(
        self,
        run_id,
        decision: HumanDecision,
        *,
        run_directory: Path,
    ) -> AgentExecutionOutcome:
        assert decision.action == "approve"
        (run_directory / "poster_round_1.png").write_bytes(b"round")
        return AgentExecutionOutcome(
            status="completed",
            result={"outcome": "improved", "rounds": [{"round_number": 1}]},
        )


def _brief() -> PosterBrief:
    return PosterBrief.model_validate(
        {
            "poster_type": "cultural_event",
            "topic": "红楼梦研讨分享会",
            "target_audience": "大学生",
            "title": "红楼梦研讨分享会",
            "event_time": "2026年7月20日 19:00",
            "location": "图书馆报告厅",
            "organizer": "文学社",
        }
    )


async def test_run_service_waits_for_human_then_resumes_and_completes(tmp_path: Path) -> None:
    service = RunService(
        repository=RunRepository(f"sqlite:///{tmp_path / 'runs.sqlite3'}"),
        artifacts=ArtifactService(tmp_path / "runs"),
        event_bus=EventBus(),
        executor=FakeExecutor(),
    )

    record = service.create(_brief())
    waiting = await service.execute(record.id)

    assert waiting.status == "waiting_for_human"
    assert service.pending(record.id).primary_issues == ["标题层级不足"]
    service.begin_decision(record.id, HumanDecision(action="approve"), expected_round_number=0)
    completed = await service.resume(record.id, HumanDecision(action="approve"))

    assert completed.status == "completed"
    assert {artifact.name for artifact in completed.artifacts} == {
        "brief.json",
        "poster_initial.png",
        "poster_round_1.png",
        "pending_human.json",
        "result.json",
    }
    assert (tmp_path / "runs" / str(record.id) / "events.jsonl").is_file()
    assert service.get(record.id).status == "completed"
