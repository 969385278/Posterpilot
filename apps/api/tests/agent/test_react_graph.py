from pathlib import Path

from app.agent.graph import create_react_round_graph
from app.agent.nodes.evaluate import evaluate_draft
from app.agent.nodes.generate_visual import generate_visual
from app.agent.nodes.render_draft import render_draft
from app.agent.tools.react_tools import ReactToolRegistry
from app.poster.renderer import PosterRenderer
from app.rag.models import KnowledgeCard, RetrievalMatch, RetrievalResult
from tests.agent.test_rendering_nodes import FakeImageProvider, _state


class OptimizationRetriever:
    async def retrieve(self, request):
        return RetrievalResult(
            query=request.query,
            candidate_ids=["title-rule"],
            matches=[
                RetrievalMatch(
                    card=KnowledgeCard(
                        id="title-rule",
                        knowledge_type="rule",
                        category="hierarchy",
                        title="标题层级",
                        content="标题应明显强于次级信息。",
                        actions=["增大标题字号"],
                        source_id="qinghua",
                        source_pages=[12],
                        review_status="approved",
                    ),
                    similarity=0.9,
                    vector_similarity=0.9,
                    lexical_similarity=0.9,
                )
            ],
        )


class SequentialReactProvider:
    def __init__(self):
        self.calls = 0
        self.messages = []

    async def complete_json(self, messages):
        self.messages.append(messages)
        self.calls += 1
        if self.calls == 1:
            return {
                "decision": "tool_call",
                "summary": "先检索标题层级依据",
                "tool_name": "search_design_knowledge",
                "arguments": {"query": "标题层级不足", "target_roles": ["title"]},
            }
        if self.calls == 2:
            assert "检索到 1 条可追溯设计知识" in str(messages)
            assert "标题应明显强于次级信息。" in str(messages)
            assert "增大标题字号" in str(messages)
            assert "retrieved_design_knowledge" in str(messages)
            return {
                "decision": "tool_call",
                "summary": "根据知识增强标题",
                "tool_name": "modify_typography",
                "arguments": {
                    "actions": [
                        {
                            "action": "set_font_size",
                            "target_id": "title",
                            "parameters": {"font_size": 108},
                            "reason": "增强标题层级",
                            "source_rule_ids": ["title-rule"],
                        }
                    ]
                },
                "knowledge_card_ids": ["title-rule"],
            }
        return {"decision": "finish_round", "summary": "本轮修改已足够"}


class EndlessReactProvider:
    def __init__(self):
        self.calls = 0

    async def complete_json(self, messages):
        self.calls += 1
        return {
            "decision": "tool_call",
            "summary": "继续微调标题",
            "tool_name": "modify_typography",
            "arguments": {
                "actions": [
                    {
                        "action": "set_font_size",
                        "target_id": "title",
                        "parameters": {"font_size": 88 + self.calls * 2},
                        "reason": "逐步增强标题",
                    }
                ]
            },
        }


async def _evaluated_state(tmp_path: Path):
    state = _state()
    generated = await generate_visual(
        state,
        image_provider=FakeImageProvider(),
        run_directory=tmp_path,
    )
    rendered = render_draft(
        {**state, **generated},
        renderer=PosterRenderer(),
        run_directory=tmp_path,
    )
    evaluated = await evaluate_draft({**state, **generated, **rendered})
    return {
        **state,
        **generated,
        **rendered,
        **evaluated,
        "human_instruction": "不要改变主视觉，只增强标题",
        "round_number": 1,
        "tool_calls_in_round": 0,
        "tool_traces": [],
    }


async def test_react_round_uses_observation_before_next_tool_and_saves_one_version(
    tmp_path: Path,
) -> None:
    provider = SequentialReactProvider()
    graph = create_react_round_graph(
        text_provider=provider,
        tools=ReactToolRegistry(OptimizationRetriever()),
        renderer=PosterRenderer(),
        run_directory=tmp_path,
    )

    result = await graph.ainvoke(await _evaluated_state(tmp_path))

    assert provider.calls == 3
    assert len(result["tool_traces"]) == 2
    assert result["tool_traces"][0].tool_name == "search_design_knowledge"
    assert result["tool_traces"][1].tool_name == "modify_typography"
    assert result["round_snapshots"][0].poster_artifact == "poster_round_1.png"
    assert (tmp_path / "poster_round_1.png").is_file()
    assert not (tmp_path / "poster_tool_1.png").exists()


async def test_react_round_forces_evaluation_after_three_tools(tmp_path: Path) -> None:
    provider = EndlessReactProvider()
    graph = create_react_round_graph(
        text_provider=provider,
        tools=ReactToolRegistry(OptimizationRetriever()),
        renderer=PosterRenderer(),
        run_directory=tmp_path,
    )

    result = await graph.ainvoke(await _evaluated_state(tmp_path))

    assert provider.calls == 3
    assert len(result["tool_traces"]) == 3
    assert len(result["round_snapshots"]) == 1
