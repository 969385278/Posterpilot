import json

import pytest

from app.experiments.memory import MemorySequence, compare_memory
from app.services.user_memory import UserMemoryService


def sequence():
    return MemorySequence.model_validate(
        {
            "id": "fixture",
            "description": "explicit update",
            "steps": [
                {
                    "id": "one",
                    "text": "以后使用蓝色",
                    "suggestions": [
                        {
                            "quote": "以后使用蓝色",
                            "key": "color",
                            "value": "蓝色",
                            "kind": "explicit",
                        },
                    ],
                    "confirmations": [{"quote": "以后使用蓝色", "key": "color", "value": "蓝色"}],
                    "checks": [{"values": {"color": "蓝色"}}],
                }
            ],
        }
    )


async def test_shared_extraction_does_not_receive_expected_profiles(tmp_path):
    calls = []

    class Provider:
        async def complete_json(self, messages):
            calls.append(messages)
            assert json.loads(messages[-1]["content"]) == {"source_text": "以后使用蓝色"}
            return {"suggestions": [item.model_dump() for item in sequence().steps[0].suggestions]}

    summary, rows = await compare_memory([sequence()], tmp_path / "run", provider=Provider())
    assert len(calls) == 1
    assert summary["conditions"]["governed"]["incorrect_steps"] == 0
    item = rows[0]["checks"][0]["profile_snapshot"]["preferences"]["color"]
    assert item["source_id"] == rows[0]["source"]["id"]
    reopened = UserMemoryService(tmp_path / "run/fixture/memory.sqlite3")
    assert reopened.profile("local")["preferences"]["color"]["value"] == "蓝色"
    assert len(reopened.events("local")["audit"]) == 1
    with pytest.raises(FileExistsError):
        await compare_memory([sequence()], tmp_path / "run")


async def test_expectation_is_scored_not_written_into_profile(tmp_path):
    case = sequence()
    case.steps[0].checks[0].values = {"color": "绿色"}
    summary, rows = await compare_memory([case], tmp_path / "run")
    assert summary["conditions"]["governed"]["incorrect_steps"] == 1
    assert rows[0]["checks"][0]["governed"] == {"color": "蓝色"}
    assert rows[0]["checks"][0]["errors"]["governed"]["color"]["expected"] == "绿色"


async def test_extraction_error_is_kept_and_invalidates_comparison(tmp_path):
    class Provider:
        async def complete_json(self, messages):
            raise RuntimeError("do not persist credentials in exception text")

    summary, rows = await compare_memory([sequence()], tmp_path / "run", provider=Provider())
    assert summary["runtime_errors"] == 1
    assert not summary["valid_governance_comparison"]
    assert summary["conditions"]["direct_overwrite"]["incorrect_steps"] == 1
    assert summary["conditions"]["governed"]["incorrect_steps"] == 1
    assert rows[0]["error"] == "memory_extraction_failed"
    assert "credentials" not in (tmp_path / "run/rows.jsonl").read_text(encoding="utf-8")


async def test_duplicate_candidates_are_not_silently_applied(tmp_path):
    case = sequence()
    case.steps[0].suggestions.append(case.steps[0].suggestions[0].model_copy())
    summary, rows = await compare_memory([case], tmp_path / "run")
    assert not summary["valid_governance_comparison"]
    assert rows[0]["checks"][0]["governed"] == {}
    assert rows[0]["checks"][0]["direct_overwrite"] == {}


@pytest.mark.parametrize("change", [
    {"value": "蓝色系"}, {"quote": "使用蓝色"}, {"scope": "campus_lecture"},
    {"kind": "temporary"}, None,
])
async def test_unmatched_confirmation_invalidates_attribution_without_inventing_approval(
    tmp_path, change,
):
    case = sequence()

    class Provider:
        async def complete_json(self, messages):
            raw = case.steps[0].suggestions[0].model_dump(mode="json")
            return {"suggestions": [{**raw, **change}] if change else []}

    summary, rows = await compare_memory([case], tmp_path / "run", provider=Provider())
    assert summary["runtime_errors"] == 0
    assert summary["unmatched_confirmation_steps"] == 1
    assert not summary["valid_governance_comparison"]
    assert rows[0]["unmatched_confirmations"] == [case.steps[0].confirmations[0].model_dump()]
    assert rows[0]["checks"][0]["governed"] == {}
    assert not any(action.get("committed") for action in rows[0]["actions"])
