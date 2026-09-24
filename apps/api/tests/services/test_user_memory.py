from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agent.user_context import personalized_brief
from app.core.exceptions import PosterPilotError
from app.main import create_app
from app.persistence.run_repository import RunRepository
from app.schemas.assistant import QuestionRequest
from app.schemas.brief import PosterBrief
from app.schemas.memory import MemoryEventInput, SourceMessageInput
from app.services.artifact_service import ArtifactService
from app.services.design_assistant import DesignAssistant
from app.services.event_bus import EventBus
from app.services.run_service import RunService
from app.services.user_memory import UserMemoryService


@pytest.fixture
def memory(tmp_path):
    return UserMemoryService(tmp_path / "memory.sqlite3")


def add(memory, *, user="local", value="低饱和", kind="explicit", scope="all", key="style"):
    source = SourceMessageInput(id=uuid4(), text=f"记住我的偏好：{value}")
    memory.save_source(user, source)
    return memory.record(
        user,
        MemoryEventInput(
            source_id=source.id,
            quote=source.text,
            key=key,
            value=value,
            kind=kind,
            scope=scope,
            confirmed=kind == "explicit",
            expected_revision=memory.profile(user)["revision"],
        ),
    )


def test_raw_source_is_immutable_and_idempotent(memory):
    source = SourceMessageInput(id=uuid4(), text="只在本次用蓝色")
    first = memory.save_source("a", source)
    assert memory.save_source("a", source) == first
    with pytest.raises(PosterPilotError, match="不可覆盖"):
        memory.save_source("a", source.model_copy(update={"text": "一直用蓝色"}))
    with pytest.raises(PosterPilotError, match="找不到"):
        memory.source("b", source.id)


def test_temporary_and_weak_preferences_never_override_confirmed(memory):
    first = add(memory)
    add(memory, value="红色", kind="temporary")
    add(memory, value="黑色", kind="weak")
    assert memory.profile("local")["preferences"]["style"]["id"] == first["id"]
    assert len(memory.events("local")["events"]) == 3


def test_unconfirmed_and_invented_quote_rejected(memory):
    source = SourceMessageInput(id=uuid4(), text="本次用蓝色")
    memory.save_source("local", source)
    with pytest.raises(ValidationError):
        MemoryEventInput(
            source_id=source.id,
            quote=source.text,
            key="color",
            value="蓝色",
            kind="explicit",
            confirmed=False,
            expected_revision=0,
        )
    with pytest.raises(PosterPilotError, match="引用必须"):
        memory.record(
            "local",
            MemoryEventInput(
                source_id=source.id,
                quote="一直用蓝色",
                key="color",
                value="蓝色",
                kind="explicit",
                confirmed=True,
                expected_revision=0,
            ),
        )
    assert memory.profile("local")["revision"] == 0


def test_revision_and_retraction_do_not_resurrect_obsolete_preference(memory):
    first = add(memory)
    second = add(memory, value="高饱和")
    assert second["supersedes"] == [first["id"]]
    with pytest.raises(PosterPilotError, match="画像已更新"):
        memory.retract("local", UUID(second["id"]), expected_revision=1, reason="改主意")
    memory.retract("local", UUID(second["id"]), expected_revision=2, reason="不再需要")
    assert memory.profile("local")["preferences"] == {}
    reopened = UserMemoryService(memory.path)
    assert reopened.profile("local")["revision"] == 3
    events = reopened.events("local")
    assert [item["state"] for item in events["events"]] == ["retracted", "superseded"]
    assert events["audit"][0]["reason"] == "不再需要"


def test_scope_specific_preference_overrides_newer_general_preference(memory):
    add(memory, value="讲座简洁", scope="campus_lecture")
    add(memory, value="一般复古")
    assert (
        memory.profile("local", scope="campus_lecture")["preferences"]["style"]["value"]
        == "讲座简洁"
    )
    assert (
        memory.profile("local", scope="club_recruitment")["preferences"]["style"]["value"]
        == "一般复古"
    )
    assert memory.profile("other")["preferences"] == {}


def test_concurrent_updates_have_exactly_one_winner(memory):
    source = SourceMessageInput(id=uuid4(), text="以后用蓝色")
    memory.save_source("local", source)
    event = MemoryEventInput(
        source_id=source.id,
        quote=source.text,
        key="color",
        value="蓝色",
        kind="explicit",
        confirmed=True,
        expected_revision=0,
    )

    def submit(_):
        try:
            memory.record("local", event)
            return "ok"
        except PosterPilotError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert sorted(results) == ["ok", "stale_memory_revision"]
    assert len(memory.events("local")["events"]) == 1


@pytest.mark.asyncio
async def test_extraction_is_proposal_only_and_checks_quotes(memory):
    class Provider:
        quote = "记住蓝色"

        async def complete_json(self, messages):
            return {
                "suggestions": [
                    {
                        "quote": self.quote,
                        "key": "color",
                        "value": "蓝色",
                        "kind": "explicit",
                        "scope": "all",
                    }
                ]
            }

    provider = Provider()
    source = SourceMessageInput(id=uuid4(), text="记住蓝色")
    result = await memory.extract("local", source, provider)
    assert result["requires_confirmation"]
    assert memory.profile("local")["preferences"] == {}
    assert memory.events("local")["events"] == []
    provider.quote = "原话没有的内容"
    with pytest.raises(PosterPilotError, match="不存在的原话"):
        await memory.extract("local", source, provider)


def make_runs(tmp_path):
    return RunService(
        repository=RunRepository(f"sqlite:///{tmp_path / 'runs.db'}"),
        artifacts=ArtifactService(tmp_path / "runs"),
        event_bus=EventBus(),
    )


def test_generation_snapshot_and_explicit_brief_priority(tmp_path):
    runs = make_runs(tmp_path)
    add(runs.memory, key="style", value="复古")
    add(runs.memory, key="color", value="蓝色")
    brief = PosterBrief(title="我的活动", use_user_memory=True, style_preferences=["极简"])
    run = runs.create(brief)
    path = runs.artifact_path(run.id, "user_context.json")
    import json

    snapshot = json.loads(path.read_text(encoding="utf-8"))
    personalized = personalized_brief(brief, snapshot)
    assert personalized.style_preferences == ["极简"]
    assert personalized.color_preferences == ["蓝色"]
    assert personalized.title == brief.title
    assert brief.color_preferences == []
    add(runs.memory, key="color", value="红色")
    assert json.loads(path.read_text(encoding="utf-8")) == snapshot
    without = runs.create(PosterBrief(title="没有开启"))
    assert "user_context.json" not in [item.name for item in without.artifacts]


def test_memory_api_lifecycle_and_user_isolation(tmp_path):
    client = TestClient(create_app(make_runs(tmp_path)))
    base = "/api/v1/datahub/users/local"
    source_id = str(uuid4())
    assert (
        client.post(base + "/sources", json={"id": source_id, "text": "以后用蓝色"}).status_code
        == 200
    )
    body = {
        "source_id": source_id,
        "quote": "以后用蓝色",
        "key": "color",
        "value": "蓝色",
        "kind": "explicit",
        "confirmed": True,
        "expected_revision": 0,
    }
    response = client.post(base + "/events", json=body)
    assert response.status_code == 200
    assert client.post(base + "/events", json=body).status_code == 409
    assert client.get("/api/v1/datahub/users/other/profile").json()["preferences"] == {}
    assert client.get(f"/api/v1/datahub/users/other/sources/{source_id}").status_code == 404
    event_id = response.json()["id"]
    assert (
        client.post(
            base + f"/events/{event_id}/retract",
            json={
                "expected_revision": 1,
                "reason": "现在不用",
            },
        ).json()["preferences"]
        == {}
    )


@pytest.mark.asyncio
async def test_assistant_memory_tools_and_conversation_isolation(tmp_path):
    runs = make_runs(tmp_path)
    item = add(runs.memory)

    class Provider:
        def __init__(self):
            self.calls = 0

        async def complete_json(self, messages):
            self.calls += 1
            if self.calls == 1:
                return {"action": "tool", "tool": "read_user_profile"}
            assert "低饱和" in messages[-1]["content"]
            return {
                "action": "answer",
                "answer": "你已确认低饱和偏好。",
                "citation_ids": [f"memory:{item['id']}"],
            }

    assistant = DesignAssistant(runs, provider=Provider())
    answer = await assistant.ask(QuestionRequest(question="我喜欢什么风格？", use_user_memory=True))
    assert answer.citations[0].excerpt == item["quote"]
    assert runs.memory.source("local", answer.memory_source_id)["text"] == answer.question
    with pytest.raises(PosterPilotError, match="另一个用户"):
        await assistant.ask(
            QuestionRequest(
                question="接着说", conversation_id=answer.conversation_id, user_id="other"
            )
        )
    assert "unavailable" in await assistant._tool("read_user_profile", "", {}, None, {})
