from uuid import uuid4

import pytest

from app.core.exceptions import PosterPilotError
from app.schemas.memory import MemoryEventInput, SourceMessageInput
from app.schemas.title_font import TITLE_FONT_ALIASES, normalize_title_font
from app.services.user_memory import UserMemoryService


@pytest.mark.parametrize("label, expected", TITLE_FONT_ALIASES.items())
def test_supported_font_labels_use_canonical_ids(label, expected):
    assert normalize_title_font(label) == expected
    assert normalize_title_font(expected) == expected


@pytest.mark.asyncio
async def test_live_font_shape_can_be_confirmed_then_consumed(tmp_path):
    memory = UserMemoryService(tmp_path / "memory.sqlite3")
    source = SourceMessageInput(id=uuid4(), text="请记住，以后标题都用马善政楷体。")

    class Provider:
        async def complete_json(self, messages):
            return {
                "suggestions": [
                    {
                        "key": "title_font",
                        "value": "马善政楷体",
                        "quote": "以后标题都用马善政楷体",
                        "kind": "explicit",
                    }
                ]
            }

    extracted = await memory.extract("test", source, Provider())
    assert memory.profile("test")["preferences"] == {}
    suggestion = extracted["suggestions"][0]
    assert suggestion["value"] == "mashanzheng"
    assert suggestion["quote"] == "以后标题都用马善政楷体"
    memory.record(
        "test",
        MemoryEventInput(source_id=source.id, expected_revision=0, confirmed=True, **suggestion),
    )
    from app.agent.user_context import personalized_brief
    from app.schemas.brief import PosterBrief

    profile = memory.profile("test")
    brief = PosterBrief(title="测试活动", user_id="test", use_user_memory=True)
    assert personalized_brief(brief, profile).title_font == "mashanzheng"
    assert (
        personalized_brief(brief.model_copy(update={"title_font": "standard"}), profile).title_font
        == "standard"
    )


@pytest.mark.asyncio
async def test_unknown_font_is_not_suggested_as_confirmable(tmp_path):
    memory = UserMemoryService(tmp_path / "memory.sqlite3")
    source = SourceMessageInput(id=uuid4(), text="以后用不存在的字体")

    class Provider:
        async def complete_json(self, messages):
            return {
                "suggestions": [
                    {
                        "key": "title_font",
                        "value": "不存在的字体",
                        "quote": source.text,
                        "kind": "explicit",
                    }
                ]
            }

    with pytest.raises(PosterPilotError) as error:
        await memory.extract("test", source, Provider())
    assert error.value.code == "invalid_memory_extraction"
    assert memory.profile("test")["revision"] == 0
    assert memory.events("test")["events"] == []
    assert memory.source("test", source.id)["text"] == source.text
