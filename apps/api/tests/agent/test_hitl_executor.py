from pathlib import Path
from uuid import uuid4

from app.agent.executor import LangGraphAgentExecutor
from app.poster.renderer import PosterRenderer
from app.rag.models import KnowledgeCard, RetrievalMatch, RetrievalResult
from app.schemas.react import HumanDecision
from tests.agent.test_generation_nodes import FakeTextProvider, _brief
from tests.agent.test_rendering_nodes import FakeImageProvider


class BothStageRetriever:
    async def retrieve(self, request):
        card = KnowledgeCard(
            id="rule-title",
            knowledge_type="rule",
            category="hierarchy",
            title="标题层级",
            content="标题必须明显强于活动信息。",
            actions=["增大标题字号"],
            intents=["generation", "optimization"],
            target_roles=["title"],
            source_id="qinghua",
            source_pages=[12],
            review_status="approved",
        )
        return RetrievalResult(
            query=request.query,
            candidate_ids=[card.id],
            matches=[
                RetrievalMatch(
                    card=card,
                    similarity=0.9,
                    vector_similarity=0.9,
                    lexical_similarity=0.9,
                )
            ],
        )


class DesignAndReactProvider:
    def __init__(self, expected_instruction: str | None = None):
        self.design = FakeTextProvider()
        self.react_calls = 0
        self.expected_instruction = expected_instruction

    async def complete_json(self, messages):
        if "ReAct Agent" not in str(messages):
            return await self.design.complete_json(messages)
        self.react_calls += 1
        if self.react_calls == 1:
            if self.expected_instruction:
                assert self.expected_instruction in str(messages)
            return {
                "decision": "tool_call",
                "summary": "增强标题层级",
                "tool_name": "modify_typography",
                "arguments": {
                    "actions": [
                        {
                            "action": "set_font_size",
                            "target_id": "title",
                            "parameters": {"font_size": 106},
                            "reason": "强化标题",
                        }
                    ]
                },
            }
        return {"decision": "finish_round", "summary": "进入复评"}


async def test_executor_pauses_resumes_one_round_and_finishes(tmp_path: Path) -> None:
    run_id = uuid4()
    executor = LangGraphAgentExecutor(
        retriever=BothStageRetriever(),
        text_provider=DesignAndReactProvider(expected_instruction="不要改变主视觉"),
        image_provider=FakeImageProvider(),
        renderer=PosterRenderer(),
    )

    started = await executor.start(
        _brief(),
        run_id=run_id,
        run_directory=tmp_path,
    )
    resumed = await executor.resume(
        run_id,
        HumanDecision(action="instruct", instruction="不要改变主视觉，只增强标题"),
        run_directory=tmp_path,
    )
    completed = await executor.resume(
        run_id,
        HumanDecision(action="finish"),
        run_directory=tmp_path,
    )

    assert started.status == "waiting_for_human"
    assert started.checkpoint.round_number == 0
    assert resumed.status == "waiting_for_human"
    assert resumed.checkpoint.round_number == 1
    assert resumed.checkpoint.tool_traces[0].tool_name == "modify_typography"
    assert (tmp_path / "poster_round_1.png").is_file()
    assert completed.status == "completed"
    assert completed.result["rounds"][0]["round_number"] == 1


async def test_executor_finishes_automatically_after_third_round(tmp_path: Path) -> None:
    run_id = uuid4()
    executor = LangGraphAgentExecutor(
        retriever=BothStageRetriever(),
        text_provider=DesignAndReactProvider(),
        image_provider=FakeImageProvider(),
        renderer=PosterRenderer(),
    )
    await executor.start(_brief(), run_id=run_id, run_directory=tmp_path)

    first = await executor.resume(
        run_id,
        HumanDecision(action="approve"),
        run_directory=tmp_path,
    )
    second = await executor.resume(
        run_id,
        HumanDecision(action="approve"),
        run_directory=tmp_path,
    )
    third = await executor.resume(
        run_id,
        HumanDecision(action="approve"),
        run_directory=tmp_path,
    )

    assert first.status == "waiting_for_human"
    assert second.status == "waiting_for_human"
    assert third.status == "completed"
    assert [item["round_number"] for item in third.result["rounds"]] == [1, 2, 3]


async def test_executor_resumes_from_sqlite_checkpoint_after_recreation(tmp_path: Path) -> None:
    run_id = uuid4()
    checkpoint_path = tmp_path / "langgraph-checkpoints.sqlite3"
    first = LangGraphAgentExecutor(
        retriever=BothStageRetriever(),
        text_provider=DesignAndReactProvider(),
        image_provider=FakeImageProvider(),
        renderer=PosterRenderer(),
        checkpoint_path=checkpoint_path,
    )

    started = await first.start(
        _brief(),
        run_id=run_id,
        run_directory=tmp_path,
    )
    await first.aclose()

    second = LangGraphAgentExecutor(
        retriever=BothStageRetriever(),
        text_provider=DesignAndReactProvider(expected_instruction="服务重启后继续增强标题"),
        image_provider=FakeImageProvider(),
        renderer=PosterRenderer(),
        checkpoint_path=checkpoint_path,
    )
    resumed = await second.resume(
        run_id,
        HumanDecision(action="instruct", instruction="服务重启后继续增强标题"),
        run_directory=tmp_path,
    )
    completed = await second.resume(
        run_id,
        HumanDecision(action="finish"),
        run_directory=tmp_path,
    )
    await second.aclose()

    assert started.status == "waiting_for_human"
    assert resumed.status == "waiting_for_human"
    assert resumed.checkpoint.round_number == 1
    assert completed.status == "completed"
    assert completed.result["rounds"][0]["round_number"] == 1
