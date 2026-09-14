import pytest

from app.agent.tools.react_tools import ReactToolRegistry, ReactToolValidationError
from app.rag.models import KnowledgeCard, RetrievalMatch, RetrievalResult
from app.schemas.react import ReactDecision
from tests.poster.test_action_validator import make_layout


class FakeRetriever:
    async def retrieve(self, request):
        assert request.intent == "optimization"
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


def _decision(tool_name: str, arguments: dict) -> ReactDecision:
    return ReactDecision(
        decision="tool_call",
        summary="测试语义工具",
        tool_name=tool_name,
        arguments=arguments,
    )


async def test_search_tool_returns_traceable_knowledge() -> None:
    result = await ReactToolRegistry(FakeRetriever()).execute(
        _decision(
            "search_design_knowledge",
            {"query": "标题不突出", "target_roles": ["title"]},
        ),
        layout=make_layout(),
    )

    assert result.layout == make_layout()
    assert result.citations[0].card_id == "title-rule"
    assert result.citations[0].source_pages == [12]
    assert "标题层级" in result.observation


async def test_typography_tool_applies_only_text_actions() -> None:
    result = await ReactToolRegistry(FakeRetriever()).execute(
        _decision(
            "modify_typography",
            {
                "actions": [
                    {
                        "action": "set_font_size",
                        "target_id": "title",
                        "parameters": {"font_size": 104},
                        "reason": "增强标题层级",
                    }
                ]
            },
        ),
        layout=make_layout(),
    )

    title = next(element for element in result.layout.elements if element.id == "title")
    assert title.font_size == 104
    assert "1 个排版动作" in result.observation


async def test_typography_tool_normalizes_common_model_shorthand() -> None:
    result = await ReactToolRegistry(FakeRetriever()).execute(
        _decision(
            "modify_typography",
            {
                "actions": [
                    {
                        "element_id": "event_info",
                        "font_size": 52,
                        "color": "#A00000",
                        "line_spacing": 1.4,
                    }
                ]
            },
        ),
        layout=make_layout(),
    )

    event_info = next(element for element in result.layout.elements if element.id == "event_info")
    assert event_info.font_size == 52
    assert event_info.color == "#A00000"
    assert event_info.line_spacing == 1.4
    assert "3 个排版动作" in result.observation


@pytest.mark.parametrize(
    "fields, message",
    [
        (
            {"font_size": 52, "color": "#A00000", "line_spacing": 1.4, "alignment": "center"},
            "at most 3 normalized",
        ),
        ({"font_size": 52, "font_weight": "bold"}, "unsupported shorthand fields"),
        ({"font_size": 52, "x": 0.1}, "provided together"),
        ({"font_size": 52, "width": 0.5}, "provided together"),
        ({"font_size": 52, "target_id": "title"}, "same element"),
    ],
)
async def test_shorthand_never_silently_drops_requested_changes(fields, message):
    layout = make_layout()
    before = layout.model_dump()
    with pytest.raises(ReactToolValidationError, match=message):
        await ReactToolRegistry(FakeRetriever()).execute(
            _decision("modify_typography", {"actions": [{"element_id": "event_info", **fields}]}),
            layout=layout,
        )
    assert layout.model_dump() == before


async def test_typography_tool_rejects_layout_action() -> None:
    with pytest.raises(ReactToolValidationError, match="modify_typography"):
        await ReactToolRegistry(FakeRetriever()).execute(
            _decision(
                "modify_typography",
                {
                    "actions": [
                        {
                            "action": "set_position",
                            "target_id": "title",
                            "parameters": {"x": 0.1, "y": 0.1},
                            "reason": "越权修改",
                        }
                    ]
                },
            ),
            layout=make_layout(),
        )


async def test_visual_tool_rejects_text_target_and_regeneration() -> None:
    registry = ReactToolRegistry(FakeRetriever())
    for action in (
        {
            "action": "set_size",
            "target_id": "main_visual",
            "parameters": {"width": 0.8, "height": 0.8},
            "reason": "模型试图缩小满版主视觉",
        },
        {
            "action": "set_size",
            "target_id": "title",
            "parameters": {"width": 0.8, "height": 0.2},
            "reason": "错误目标",
        },
        {
            "action": "regenerate_visual",
            "target_id": "main_visual",
            "parameters": {},
            "reason": "不允许重新生图",
        },
    ):
        with pytest.raises(ReactToolValidationError, match="modify_visual"):
            await registry.execute(
                _decision("modify_visual", {"actions": [action]}),
                layout=make_layout(),
            )


async def test_layout_tool_rejects_out_of_bounds_result() -> None:
    with pytest.raises(ValueError, match="canvas"):
        await ReactToolRegistry(FakeRetriever()).execute(
            _decision(
                "modify_layout",
                {
                    "actions": [
                        {
                            "action": "set_position",
                            "target_id": "title",
                            "parameters": {"x": 0.95, "y": 0.1},
                            "reason": "移出画布",
                        }
                    ]
                },
            ),
            layout=make_layout(),
        )
