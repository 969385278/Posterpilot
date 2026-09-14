from pathlib import Path

from sqlalchemy.engine import make_url

from app.agent.nodes.plan_design import _normalize_design_payload
from app.core.config import Settings
from app.core.paths import PROJECT_ROOT
from app.schemas.brief import PosterBrief


def test_defaults_do_not_follow_working_directory(monkeypatch, tmp_path):
    for key in ("POSTERPILOT_DATA_DIR", "POSTERPILOT_DATABASE_URL", "LANGGRAPH_CHECKPOINT_PATH"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None)
    assert settings.data_dir == PROJECT_ROOT / "data"
    assert settings.langgraph_checkpoint_path == PROJECT_ROOT / "data/langgraph-checkpoints.sqlite3"
    assert (
        Path(make_url(settings.database_url).database) == PROJECT_ROOT / "data/posterpilot.sqlite3"
    )
    assert Settings.model_config["env_file"] == PROJECT_ROOT / ".env"
    assert list(tmp_path.iterdir()) == []


def test_explicit_relative_and_absolute_storage_paths(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    settings = Settings(
        _env_file=None,
        data_dir="custom-data",
        LANGGRAPH_CHECKPOINT_PATH=tmp_path / "checkpoint.sqlite3",
        database_url="sqlite:///custom-data/runs.sqlite3?timeout=15",
    )
    assert settings.data_dir == PROJECT_ROOT / "custom-data"
    assert settings.langgraph_checkpoint_path == tmp_path / "checkpoint.sqlite3"
    url = make_url(settings.database_url)
    assert Path(url.database) == PROJECT_ROOT / "custom-data/runs.sqlite3"
    assert url.query["timeout"] == "15"


def test_special_database_urls_are_preserved():
    for url in (
        "sqlite://",
        "sqlite:///:memory:",
        "sqlite:///file:memdb1?mode=memory&cache=shared&uri=true",
        "postgresql://user:password@localhost/database",
    ):
        assert Settings(_env_file=None, database_url=url).database_url == url


def test_absolute_sqlite_path_is_preserved(tmp_path):
    database = tmp_path / "runs.sqlite3"
    settings = Settings(_env_file=None, database_url=f"sqlite:///{database.as_posix()}")
    assert Path(make_url(settings.database_url).database) == database


def test_actual_design_normalization_loads_templates_from_another_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    brief = PosterBrief.model_validate(
        {
            "poster_type": "club_recruitment",
            "topic": "社团招新",
            "target_audience": "大学生",
            "title": "加入摄影社",
            "event_time": "周六下午",
            "location": "学生活动中心",
            "organizer": "摄影社",
        }
    )
    payload = _normalize_design_payload({}, brief, approved_refs=set())
    elements = {element["role"]: element for element in payload["layout"]["elements"]}
    assert elements["title"]["content"] == "加入摄影社"
    assert "周六下午" in elements["event_info"]["content"]
    assert list(tmp_path.iterdir()) == []
