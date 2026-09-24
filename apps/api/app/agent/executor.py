import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from app.agent.graph import create_hitl_react_graph
from app.agent.nodes.evaluate import EvaluationDependencies
from app.agent.nodes.retrieve_knowledge import Retriever
from app.agent.state import initial_agent_state
from app.agent.tools.react_tools import ReactToolRegistry
from app.poster.renderer import PosterRenderer
from app.providers.image.base import ImageProvider
from app.providers.llm.base import JsonChatProvider
from app.schemas.brief import PosterBrief
from app.schemas.react import AgentExecutionOutcome, HumanCheckpoint, HumanDecision


class AgentStateNotFoundError(RuntimeError):
    pass


class LangGraphAgentExecutor:
    """Run one persisted LangGraph thread with native human interrupts."""

    def __init__(
        self,
        *,
        retriever: Retriever,
        text_provider: JsonChatProvider,
        image_provider: ImageProvider,
        renderer: PosterRenderer,
        evaluation: EvaluationDependencies | None = None,
        checkpoint_path: Path | str | None = None,
        experience_source: Any | None = None,
        asset_source: Any | None = None,
    ) -> None:
        self.retriever = retriever
        self.text_provider = text_provider
        self.image_provider = image_provider
        self.renderer = renderer
        self.evaluation = evaluation
        self.tools = ReactToolRegistry(retriever)
        self.experience_source = experience_source
        self.asset_source = asset_source
        self.event_sink = None
        self.checkpoint_path = Path(checkpoint_path).resolve() if checkpoint_path else None
        self._graph: Any | None = None
        self._sqlite_context: Any | None = None
        self._graph_lock = asyncio.Lock()

    async def start(
        self,
        brief: PosterBrief,
        *,
        run_id: UUID,
        run_directory: Path,
    ) -> AgentExecutionOutcome:
        graph = await self._ensure_graph()
        initial = initial_agent_state(brief)
        initial["run_id"] = str(run_id)
        initial["run_directory"] = str(Path(run_directory).resolve())
        profile_path = Path(run_directory) / "user_context.json"
        if brief.use_user_memory and profile_path.exists():
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            if profile.get("user_id") != brief.user_id:
                raise ValueError("Profile snapshot belongs to a different user")
            initial["user_context"] = profile
        result = await graph.ainvoke(initial, config=self._config(run_id))
        return self._outcome(result, event_start=0)

    async def resume(
        self,
        run_id: UUID,
        decision: HumanDecision,
        *,
        run_directory: Path,
    ) -> AgentExecutionOutcome:
        graph = await self._ensure_graph()
        config = self._config(run_id)
        snapshot = await graph.aget_state(config)
        if not snapshot.values:
            raise AgentStateNotFoundError(f"No persisted Agent state for run {run_id}.")
        saved_directory = snapshot.values.get("run_directory")
        expected_directory = Path(run_directory).resolve()
        if not saved_directory or Path(str(saved_directory)).resolve() != expected_directory:
            raise AgentStateNotFoundError(f"Persisted Agent state does not match run {run_id}.")
        if not any(task.interrupts for task in snapshot.tasks):
            raise AgentStateNotFoundError(f"Run {run_id} is not paused for human input.")
        event_start = len(snapshot.values.get("events", []))
        result = await graph.ainvoke(
            Command(resume=decision.model_dump(mode="json")),
            config=config,
        )
        return self._outcome(result, event_start=event_start)

    async def aclose(self) -> None:
        if self._sqlite_context is not None:
            await self._sqlite_context.__aexit__(None, None, None)
            self._sqlite_context = None
        self._graph = None

    async def _ensure_graph(self):
        if self._graph is not None:
            return self._graph
        async with self._graph_lock:
            if self._graph is not None:
                return self._graph
            if self.checkpoint_path is None:
                checkpointer = InMemorySaver()
            else:
                self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
                context = AsyncSqliteSaver.from_conn_string(str(self.checkpoint_path))
                checkpointer = await context.__aenter__()
                await checkpointer.setup()
                self._sqlite_context = context
            self._graph = create_hitl_react_graph(
                retriever=self.retriever,
                text_provider=self.text_provider,
                image_provider=self.image_provider,
                renderer=self.renderer,
                tools=self.tools,
                checkpointer=checkpointer,
                evaluation=self.evaluation,
                experience_source=self.experience_source,
                asset_source=self.asset_source,
                event_sink=self.event_sink,
            )
            return self._graph

    @staticmethod
    def _config(run_id: UUID) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": str(run_id)}}

    @staticmethod
    def _outcome(result: dict[str, Any], *, event_start: int) -> AgentExecutionOutcome:
        events = [event for event in result.get("events", [])[event_start:]
                  if not event.get("_streamed")]
        interrupts = result.get("__interrupt__", ())
        if interrupts:
            checkpoint = HumanCheckpoint.model_validate(interrupts[0].value)
            return AgentExecutionOutcome(
                status="waiting_for_human",
                checkpoint=checkpoint,
                events=events,
            )
        payload = result.get("result")
        if not isinstance(payload, dict):
            raise RuntimeError("Agent graph completed without a result payload.")
        return AgentExecutionOutcome(
            status="completed",
            result=payload,
            events=events,
        )
