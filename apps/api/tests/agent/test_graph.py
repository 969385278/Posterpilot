from app.agent.graph import create_generation_graph
from app.agent.state import initial_agent_state
from app.schemas.brief import PosterBrief
from tests.agent.test_generation_nodes import FakeRetriever, FakeTextProvider


async def test_generation_graph_executes_retrieval_then_design_plan() -> None:
    graph = create_generation_graph(retriever=FakeRetriever(), text_provider=FakeTextProvider())
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

    result = await graph.ainvoke(initial_agent_state(brief))

    assert result["design_spec"].template_id == "cultural_event"
    assert [event["node"] for event in result["events"]] == [
        "retrieve_generation_knowledge",
        "plan_design",
    ]
