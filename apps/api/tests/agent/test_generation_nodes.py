from app.agent.nodes.plan_design import plan_design
from app.agent.nodes.retrieve_knowledge import retrieve_generation_knowledge
from app.agent.state import initial_agent_state
from app.rag.models import KnowledgeCard, RetrievalMatch, RetrievalResult
from app.schemas.brief import PosterBrief


class FakeRetriever:
    async def retrieve(self, request):
        assert request.intent == "generation"
        return RetrievalResult(
            query=request.query,
            candidate_ids=["rule-title"],
            matches=[
                RetrievalMatch(
                    card=KnowledgeCard(
                        id="rule-title",
                        knowledge_type="rule",
                        category="hierarchy",
                        title="标题层级",
                        content="标题必须明显强于活动信息。",
                        actions=["增大标题字号"],
                        source_id="qinghua",
                        source_pages=[1],
                        review_status="approved",
                    ),
                    similarity=0.9,
                    vector_similarity=0.9,
                    lexical_similarity=0.9,
                )
            ],
        )


class FakeTextProvider:
    async def complete_json(self, messages):
        assert "标题层级" in str(messages)
        return {
            "design_goal": "突出活动主题和时间地点",
            "template_id": "cultural_event",
            "expected_attention_path": ["title", "main_visual", "event_info"],
            "layout": {
                "canvas": {"width": 1080, "height": 1440},
                "elements": [
                    {
                        "id": "title",
                        "role": "title",
                        "content": "红楼梦研讨分享会",
                        "box": {"x": 0.08, "y": 0.07, "width": 0.84, "height": 0.15},
                        "font_size": 88,
                    },
                    {
                        "id": "visual",
                        "role": "main_visual",
                        "box": {"x": 0.08, "y": 0.31, "width": 0.84, "height": 0.43},
                    },
                    {
                        "id": "event-info",
                        "role": "event_info",
                        "content": "2026年7月20日 19:00\\n图书馆报告厅",
                        "box": {"x": 0.08, "y": 0.79, "width": 0.84, "height": 0.1},
                        "font_size": 32,
                    },
                ],
            },
            "palette": {"background": "#E8DDC7", "primary": "#7A2330", "secondary": "#4A4038"},
            "visual_prompt": "classical Chinese literature mood, no text",
            "knowledge_refs": ["rule-title", "invented-rule"],
        }


class DriftingTextProvider:
    async def complete_json(self, messages):
        return {
            "design_goal": "突出古典文学主题和活动信息",
            "template_id": "classic_lecture_poster",
            "expected_attention_path": "标题→主视觉→时间地点→主办方",
            "layout": {
                "type": "vertical_split",
                "title_position": "top",
                "visual_position": "center",
            },
            "palette": {
                "primary": "#8B0000",
                "secondary": "#F5F1E8",
                "accent": "#1C1C1C",
            },
            "visual_prompt": "classical Chinese garden and book texture, no text",
            "negative_prompt": "modern neon, cartoon",
            "knowledge_refs": ["rule-title"],
        }


def _brief() -> PosterBrief:
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


async def test_generation_nodes_retrieve_knowledge_and_validate_design_spec() -> None:
    state = initial_agent_state(_brief())

    retrieved = await retrieve_generation_knowledge(state, retriever=FakeRetriever())
    planned = await plan_design({**state, **retrieved}, text_provider=FakeTextProvider())

    assert retrieved["retrieval_generation"].matches[0].card.id == "rule-title"
    assert planned["design_spec"].template_id == "cultural_event"
    assert planned["design_spec"].knowledge_refs == ["rule-title"]
    assert [event["node"] for event in planned["events"]] == [
        "retrieve_generation_knowledge",
        "plan_design",
    ]


async def test_plan_design_normalizes_real_model_schema_drift_to_safe_template() -> None:
    state = initial_agent_state(_brief())
    retrieved = await retrieve_generation_knowledge(state, retriever=FakeRetriever())

    planned = await plan_design({**state, **retrieved}, text_provider=DriftingTextProvider())

    design = planned["design_spec"]
    assert design.template_id == "cultural_event"
    assert design.layout.canvas.model_dump() == {"width": 1080, "height": 1440}
    assert [element.role for element in design.layout.elements] == [
        "title",
        "main_visual",
        "event_info",
        "organizer",
    ]
    assert design.expected_attention_path == ["title", "main_visual", "event_info", "organizer"]
    assert design.palette.background == "#F5F1E8"
    assert design.knowledge_refs == ["rule-title"]
