from types import SimpleNamespace

import pytest

from app.agent.tools.react_tools import ReactToolRegistry, ReactToolValidationError
from app.core.exceptions import PosterPilotError
from app.experiments.toolsets import RestrictedToolset, compare_capabilities
from app.schemas.react import ReactDecision
from tests.poster.test_action_validator import make_layout
from tests.services.test_decision_experiment import FinishProvider, hub, make_task
from tests.services.test_user_memory import make_runs


def test_pair_counts_keep_regressions_errors_and_publication_evidence_separate():
    from app.experiments.toolsets import summarize_tool_pairs

    def pair(base, extended, *, published=True, error=None):
        return {
            "conditions": {
                "base_tools": {"accepted_round": base, "error_type": error},
                "extended_tools": {
                    "accepted_round": extended,
                    "rounds": [
                        {
                            "snapshot": {
                                "tool_traces": [
                                    {
                                        "success": True,
                                        "tool_name": "set_text_opacity",
                                        "tool_publication": {"revision": 1} if published else None,
                                    }
                                ],
                            }
                        }
                    ],
                },
            }
        }

    result = summarize_tool_pairs(
        [
            pair(None, 1),
            pair(1, None),
            pair(None, 1, published=False),
            pair(None, 1, error="TimeoutError"),
            {"conditions": {}, "error_type": "ValueError"},
        ],
        ["set_text_opacity"],
    )
    assert result["assessable_pairs"] == 3 and result["error_pairs"] == 2
    assert result["newly_solved"] == 2 and result["regressed"] == 1
    assert result["newly_solved_with_successful_added_tool"] == 1


async def test_hidden_tool_cannot_be_executed_by_guessing_its_name():
    calls = []

    async def execute(*args, **kwargs):
        calls.append(args)

    source = SimpleNamespace(
        public_catalog=lambda: [{"name": "modify_layout"}, {"name": "set_text_opacity"}],
        execute=execute,
    )
    restricted = RestrictedToolset(source, {"modify_layout"})
    assert restricted.public_catalog() == [{"name": "modify_layout"}]
    with pytest.raises(ReactToolValidationError, match="excluded"):
        await restricted.execute(
            ReactDecision(
                decision="tool_call",
                summary="不应越过实验条件",
                tool_name="set_text_opacity",
                arguments={"target_ids": ["title"], "opacity": 0.8},
            ),
            layout=make_layout(),
        )
    assert calls == []


async def test_experiment_does_not_grant_permission_to_unpublished_extension(tmp_path):
    registry = ReactToolRegistry(None)
    registry.release_source = make_runs(tmp_path).harness
    with pytest.raises(PosterPilotError) as error:
        await compare_capabilities(
            [make_task(tmp_path)],
            tmp_path / "experiment",
            provider=FinishProvider(),
            tools=registry,
            hub=hub(),
            added_tools=["set_text_opacity"],
        )
    assert error.value.code == "tool_not_published"
    assert registry.release_source.catalog()[-1]["status"] != "published"


async def test_condition_still_uses_real_registry_authorization(tmp_path):
    registry = ReactToolRegistry(None)
    registry.release_source = make_runs(tmp_path).harness
    restricted = RestrictedToolset(registry, {"set_text_opacity"})
    with pytest.raises(PosterPilotError):
        await restricted.execute(
            ReactDecision(
                decision="tool_call",
                summary="允许列表不能代替工具发布",
                tool_name="set_text_opacity",
                arguments={"target_ids": ["title"], "opacity": 0.8},
            ),
            layout=make_layout(),
        )
