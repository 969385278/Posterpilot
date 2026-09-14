from pathlib import Path

from app.persistence.run_repository import RunRepository
from app.schemas.brief import PosterBrief
from app.persistence.models import RunRow
from sqlalchemy import update


def make_brief() -> PosterBrief:
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


def test_repository_creates_and_reads_run(tmp_path: Path) -> None:
    repository = RunRepository(f"sqlite:///{tmp_path / 'runs.sqlite3'}")

    created = repository.create(make_brief())
    loaded = repository.get(created.id)

    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.status == "queued"
    assert loaded.brief.title == "红楼梦研讨分享会"


def test_repository_updates_current_node_and_status(tmp_path: Path) -> None:
    repository = RunRepository(f"sqlite:///{tmp_path / 'runs.sqlite3'}")
    created = repository.create(make_brief())

    running = repository.update_status(created.id, "running", current_node="parse_brief")
    completed = repository.update_status(created.id, "completed", current_node="finalize")

    assert running.status == "running"
    assert running.current_node == "parse_brief"
    assert completed.status == "completed"
    assert completed.current_node == "finalize"
    assert completed.updated_at >= created.updated_at


def test_repository_lists_newest_runs_first(tmp_path: Path) -> None:
    repository = RunRepository(f"sqlite:///{tmp_path / 'runs.sqlite3'}")
    first = repository.create(make_brief())
    second = repository.create(make_brief())

    runs = repository.list(limit=10)

    assert [run.id for run in runs] == [second.id, first.id]


def test_repository_breaks_identical_timestamp_ties_by_insertion(tmp_path: Path) -> None:
    repository = RunRepository(f"sqlite:///{tmp_path / 'ties.sqlite3'}")
    created = [repository.create(make_brief()) for _ in range(5)]
    with repository.database.session() as session:
        session.execute(update(RunRow).values(created_at=created[0].created_at))
        session.commit()
    assert [run.id for run in repository.list()] == [run.id for run in reversed(created)]
