from pathlib import Path

from app.agent.graph import create_optimization_graph
from app.agent.state import initial_agent_state
from app.poster.renderer import PosterRenderer
from app.rag.models import RetrievalRequest, RetrievalResult
from app.schemas.brief import PosterBrief
from tests.agent.test_generation_nodes import FakeRetriever, FakeTextProvider
from tests.agent.test_optimization_nodes import FakeOptimizationProvider
from tests.agent.test_rendering_nodes import FakeImageProvider


class FullRetriever:
    def __init__(self) -> None:
        self.generation = FakeRetriever()

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        if request.intent == "generation":
            return await self.generation.retrieve(request)
        return RetrievalResult(query=request.query, candidate_ids=[])


class FullTextProvider:
    def __init__(self) -> None:
        self.design = FakeTextProvider()
        self.optimization = FakeOptimizationProvider()

    async def complete_json(self, messages):
        if "OptimizationPlan" in str(messages):
            return await self.optimization.complete_json(messages)
        return await self.design.complete_json(messages)


async def test_full_graph_generates_evaluates_optimizes_and_finalizes(tmp_path: Path) -> None:
    brief = PosterBrief.model_validate(
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
    graph = create_optimization_graph(
        retriever=FullRetriever(),
        text_provider=FullTextProvider(),
        image_provider=FakeImageProvider(),
        renderer=PosterRenderer(),
        run_directory=str(tmp_path),
    )

    result = await graph.ainvoke(initial_agent_state(brief))

    assert Path(result["poster_initial_path"]).is_file()
    assert Path(result["poster_optimized_path"]).is_file()
    assert result["result"]["outcome"] in {"improved", "unchanged", "declined"}
    assert [event["node"] for event in result["events"]] == [
        "retrieve_generation_knowledge",
        "plan_design",
        "generate_visual",
        "render_draft",
        "evaluate_draft",
        "retrieve_optimization_knowledge",
        "plan_optimization",
        "apply_optimization",
        "evaluate_optimized",
        "finalize",
    ]
