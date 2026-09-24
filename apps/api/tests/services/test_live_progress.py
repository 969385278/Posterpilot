import asyncio
from pathlib import Path

from app.agent.executor import LangGraphAgentExecutor
from app.persistence.run_repository import RunRepository
from app.poster.renderer import PosterRenderer
from app.schemas.react import HumanDecision
from app.services.artifact_service import ArtifactService
from app.services.event_bus import EventBus
from app.services.run_service import RunService
from tests.agent.test_generation_nodes import _brief
from tests.agent.test_hitl_executor import BothStageRetriever, DesignAndReactProvider
from tests.agent.test_rendering_nodes import FakeImageProvider


class WaitingImage(FakeImageProvider):
    def __init__(self):
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def generate(self, *args, **kwargs):
        self.entered.set()
        await self.release.wait()
        return await super().generate(*args, **kwargs)


def make_service(root: Path, image):
    executor = LangGraphAgentExecutor(
        retriever=BothStageRetriever(),
        text_provider=DesignAndReactProvider(),
        image_provider=image,
        renderer=PosterRenderer(),
        checkpoint_path=root / "graph.sqlite3",
    )
    return RunService(
        repository=RunRepository(f"sqlite:///{root / 'runs.sqlite3'}"),
        artifacts=ArtifactService(root / "runs"),
        event_bus=EventBus(),
        executor=executor,
        data_origin="offline_demo",
    )


async def test_progress_precedes_image_completion_and_does_not_duplicate_on_resume(tmp_path):
    image = WaitingImage()
    service = make_service(tmp_path, image)
    run = service.create(_brief().model_copy(update={"attention_layout": False}))
    queue = service.event_bus.subscribe(run.id)
    worker = asyncio.create_task(service.execute(run.id))
    try:
        await asyncio.wait_for(image.entered.wait(), timeout=10)
        assert not worker.done()
        visible = []
        while not queue.empty():
            visible.append(queue.get_nowait())
        assert any(
            item.type == "node_started" and item.node == "generate_visual" for item in visible
        )
        assert any(item.type == "node_completed" and item.node == "plan_design" for item in visible)
    finally:
        image.release.set()
    result = await asyncio.wait_for(worker, timeout=15)
    assert result.status == "waiting_for_human"
    decision = HumanDecision(action="instruct", instruction="增强标题")
    service.begin_decision(run.id, decision, expected_round_number=0)
    resumed = await service.resume(run.id, decision)
    assert resumed.status == "waiting_for_human"
    events = service.events(run.id)
    assert sum(item.node == "plan_design" and item.type == "node_completed" for item in events) == 1
    assert (
        sum(item.node == "modify_typography" and item.type == "tool_started" for item in events)
        == 1
    )
    assert (
        sum(item.node == "modify_typography" and item.type == "tool_completed" for item in events)
        == 1
    )
    ids = [item.id for item in events]
    service.event_bus.unsubscribe(run.id, queue)
    await service.aclose()

    restored = make_service(tmp_path, FakeImageProvider())
    try:
        finish = HumanDecision(action="finish")
        restored.begin_decision(run.id, finish, expected_round_number=1)
        assert (await restored.resume(run.id, finish)).status == "completed"
        assert [item.id for item in restored.events(run.id)][: len(ids)] == ids
        assert (
            sum(
                item.node == "plan_design" and item.type == "node_completed"
                for item in restored.events(run.id)
            )
            == 1
        )
    finally:
        await restored.aclose()


async def test_progress_sink_failure_keeps_graph_success_and_returns_undelivered_events(tmp_path):
    from uuid import uuid4

    service = make_service(tmp_path, FakeImageProvider())

    def broken(*args):
        raise RuntimeError("event projection unavailable")

    service.executor.event_sink = broken
    try:
        result = await service.executor.start(
            _brief().model_copy(update={"attention_layout": False}),
            run_id=uuid4(),
            run_directory=tmp_path,
        )
        assert result.status == "waiting_for_human"
        assert any(item["node"] == "plan_design" for item in result.events)
        assert not any(item.get("_streamed") for item in result.events)
    finally:
        await service.aclose()
