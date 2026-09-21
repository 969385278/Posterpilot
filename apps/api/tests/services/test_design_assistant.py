from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import PosterPilotError
from app.main import create_app
from app.persistence.run_repository import RunRepository
from app.rag.models import KnowledgeCard, RetrievalMatch, RetrievalResult
from app.schemas.assistant import QuestionRequest
from app.schemas.brief import PosterBrief
from app.schemas.react import AgentExecutionOutcome, HumanCheckpoint
from app.services.artifact_service import ArtifactService
from app.services.design_assistant import DesignAssistant
from app.services.event_bus import EventBus
from app.services.run_service import RunService


class Provider:
    def __init__(self, steps):
        self.steps = iter(steps)
        self.messages = []

    async def complete_json(self, messages):
        self.messages.append(list(messages))
        return next(self.steps)


class Executor:
    async def start(self, brief, *, run_id, run_directory):
        return AgentExecutionOutcome(
            status="waiting_for_human",
            checkpoint=HumanCheckpoint(
                round_number=0, score=60, primary_issues=["标题层级不足"], suggestion="增加标题字号"
            ),
        )

    async def resume(self, run_id, decision, *, run_directory):
        return AgentExecutionOutcome(
            status="waiting_for_human",
            checkpoint=HumanCheckpoint(round_number=1, score=65, suggestion="请检查结果"),
        )


def setup(tmp_path, steps):
    runs = RunService(
        repository=RunRepository(f"sqlite:///{tmp_path / 'runs.sqlite3'}"),
        artifacts=ArtifactService(tmp_path / "runs"),
        event_bus=EventBus(),
        executor=Executor(),
    )
    provider = Provider(steps)
    assistant = DesignAssistant(runs, provider=provider)
    runs.design_assistant = assistant
    return runs, assistant, provider


def answer(**kwargs):
    return {"action": "answer", "answer": "标题与正文需要形成层级。", **kwargs}


@pytest.mark.asyncio
async def test_read_only_then_explicit_confirmation_and_stale_rejection(tmp_path):
    runs, assistant, provider = setup(
        tmp_path,
        [
            {"action": "tool", "tool": "inspect_poster"},
            answer(proposal={"scope": "typography", "instruction": "增大标题字号，保留主视觉"}),
        ],
    )
    run = runs.create(PosterBrief(title="社团招新"))
    await runs.execute(run.id)
    response = await assistant.ask(QuestionRequest(question="标题为什么不醒目？", run_id=run.id))
    assert response.trace[0].tool == "inspect_poster"
    assert "标题层级不足" in provider.messages[-1][-1]["content"]
    assert runs.get(run.id).status == "waiting_for_human"
    assert response.round_number == 0 and response.proposal
    record, decision = assistant.confirm(response.id)
    assert record.status == "running" and decision.instruction == "增大标题字号，保留主视觉"
    await runs.resume(run.id, decision)
    with pytest.raises(PosterPilotError):
        assistant.confirm(response.id)


@pytest.mark.asyncio
async def test_grounded_citations_and_follow_up(tmp_path):
    card = KnowledgeCard(
        id="hierarchy",
        knowledge_type="rule",
        title="视觉层级",
        content="标题与正文保持字号差异",
        category="layout",
        actions=["放大标题"],
        source_id="design.pdf",
        source_pages=[3],
        review_status="approved",
    )

    class Retriever:
        async def retrieve(self, request):
            return RetrievalResult(
                query=request.query,
                matches=[
                    RetrievalMatch(
                        card=card, similarity=0.8, vector_similarity=0.8, lexical_similarity=0.5
                    )
                ],
            )

    runs, assistant, provider = setup(
        tmp_path,
        [
            {"action": "tool", "tool": "search_knowledge"},
            answer(citation_ids=["hierarchy", "invented"]),
            answer(),
        ],
    )
    runs.executor.retriever = Retriever()
    first = await assistant.ask(QuestionRequest(question="标题层级怎么安排？"))
    assert [c.id for c in first.citations] == ["hierarchy"]
    second = await assistant.ask(
        QuestionRequest(question="那正文呢？", conversation_id=first.conversation_id)
    )
    assert second.conversation_id == first.conversation_id
    assert len(assistant.repository.history(first.conversation_id)) == 2
    assert any(m["content"] == "标题层级怎么安排？" for m in provider.messages[-1])
    assert DesignAssistant(runs).repository.get(first.id).answer == first.answer


@pytest.mark.asyncio
async def test_no_poster_cannot_propose_mutation(tmp_path):
    _, assistant, _ = setup(
        tmp_path, [answer(proposal={"scope": "typography", "instruction": "改标题"})]
    )
    result = await assistant.ask(QuestionRequest(question="改标题"))
    assert result.proposal is None


@pytest.mark.asyncio
async def test_invalid_tool_and_model_failure_are_explicit(tmp_path):
    _, assistant, _ = setup(tmp_path, [{"action": "tool", "tool": "delete_files"}])
    result = await assistant.ask(QuestionRequest(question="删除全部文件"))
    assert result.degraded and result.proposal is None and not result.trace


@pytest.mark.asyncio
async def test_tool_budget_is_bounded(tmp_path):
    _, assistant, provider = setup(
        tmp_path, [{"action": "tool", "tool": "read_history", "query": str(i)} for i in range(6)]
    )
    result = await assistant.ask(QuestionRequest(question="分析"))
    assert len(result.trace) == 4 and len(provider.messages) == 5 and result.degraded


@pytest.mark.asyncio
async def test_conversation_cannot_switch_run(tmp_path):
    runs, assistant, _ = setup(tmp_path, [answer()])
    result = await assistant.ask(QuestionRequest(question="字体怎么选？"))
    run = runs.create(PosterBrief(title="另一个任务"))
    with pytest.raises(PosterPilotError):
        await assistant.ask(
            QuestionRequest(question="继续", run_id=run.id, conversation_id=result.conversation_id)
        )


@pytest.mark.asyncio
async def test_case_tool_uses_approved_retrieval_contract(tmp_path):
    runs, assistant, _ = setup(
        tmp_path, [{"action": "tool", "tool": "search_cases"}, answer(citation_ids=["case:abc"])]
    )
    calls = []

    def retrieve(request):
        calls.append(request)
        return [
            {
                "case_id": "abc",
                "problem": "标题小",
                "lesson": "增强标题层级",
                "source": "/api/v1/datahub/cases/abc",
            }
        ]

    runs.datahub.retrieve = retrieve
    response = await assistant.ask(QuestionRequest(question="有没有招新案例？"))
    assert all(not call.include_demo for call in calls)
    assert response.citations[0].excerpt == "增强标题层级"


@pytest.mark.asyncio
async def test_image_tool_sends_current_registered_image(tmp_path):
    runs, assistant, _ = setup(tmp_path, [{"action": "tool", "tool": "analyze_image"}, answer()])
    run = runs.create(PosterBrief(title="招新"))
    await runs.execute(run.id)
    reference = runs.artifacts.write_bytes(run.id, "poster_initial.png", b"image fixture")
    runs.repository.add_artifact(run.id, reference)
    checkpoint = runs.pending(run.id)
    checkpoint.poster_artifact = "poster_initial.png"
    runs.artifacts.write_json(run.id, "pending_human.json", checkpoint.model_dump(mode="json"))
    calls = []

    class Vision:
        async def analyze_json(self, **kwargs):
            calls.append(kwargs)
            return {"observations": ["颜色对比明显"]}

    runs.executor.evaluation = SimpleNamespace(vision=SimpleNamespace(provider=Vision()))
    response = await assistant.ask(QuestionRequest(question="颜色怎么样？", run_id=run.id))
    assert response.trace[0].success
    assert calls[0]["image_url"].startswith("data:image/png;base64,")
    assert "颜色怎么样" in calls[0]["prompt"]


def test_api_round_trip_and_validation(tmp_path):
    runs, _, _ = setup(tmp_path, [answer()])
    with TestClient(create_app(run_service=runs)) as client:
        response = client.post("/api/v1/assistant/questions", json={"question": "怎样配色？"})
        assert response.status_code == 200
        conversation = client.get(
            f"/api/v1/assistant/conversations/{response.json()['conversation_id']}"
        )
        assert conversation.json()[0]["question"] == "怎样配色？"
        assert client.post("/api/v1/assistant/questions", json={"question": " "}).status_code == 422
        assert client.post(f"/api/v1/assistant/answers/{uuid4()}/confirm").status_code == 404


@pytest.mark.asyncio
async def test_unsupported_visual_regeneration_is_not_confirmable(tmp_path):
    _, assistant, _ = setup(
        tmp_path,
        [
            answer(
                proposal={
                    "scope": "visual_regenerate",
                    "instruction": "重新画人物",
                }
            )
        ],
    )
    response = await assistant.ask(QuestionRequest(question="重新画人物"))
    assert response.degraded and response.proposal is None


@pytest.mark.asyncio
async def test_offline_mode_does_not_pretend_to_call_model(tmp_path):
    runs, assistant, provider = setup(tmp_path, [answer()])
    runs.data_origin = "offline_demo"
    response = await assistant.ask(QuestionRequest(question="帮我分析海报"))
    assert response.degraded and not provider.messages
    assert "离线演示" in response.answer
