from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from app.core.exceptions import PosterPilotError
from app.persistence.run_repository import RunNotFoundError, RunRepository
from app.schemas.brief import PosterBrief
from app.schemas.react import AgentExecutionOutcome, HumanCheckpoint, HumanDecision
from app.schemas.run import RunEvent, RunRecord
from app.schemas.layout import PosterLayout
from app.poster.design_guards import DesignConstraintError, assert_design_constraints, assert_rendered_locks, validate_control_targets
from app.services.artifact_service import SAFE_ARTIFACT_NAME, ArtifactService
from app.services.event_bus import EventBus
from app.rag.case_repository import CaseRepository
from app.poster.template_loader import TemplateLoader
from app.schemas.design_control import DesignControls

logger = logging.getLogger(__name__)


class AgentExecutor(Protocol):
    async def start(
        self,
        brief: PosterBrief,
        *,
        run_id: UUID,
        run_directory: Path,
    ) -> AgentExecutionOutcome: ...

    async def resume(
        self,
        run_id: UUID,
        decision: HumanDecision,
        *,
        run_directory: Path,
    ) -> AgentExecutionOutcome: ...


class RunService:
    def __init__(
        self,
        *,
        repository: RunRepository,
        artifacts: ArtifactService,
        event_bus: EventBus,
        executor: AgentExecutor | None = None,
    ) -> None:
        self.repository = repository
        self.artifacts = artifacts
        self.event_bus = event_bus
        self.executor = executor

    @property
    def can_execute(self) -> bool:
        return self.executor is not None

    async def aclose(self) -> None:
        if self.executor is None:
            return
        close = getattr(self.executor, "aclose", None)
        if close is not None:
            await close()

    def create(self, brief: PosterBrief) -> RunRecord:
        if brief.attention_priority:
            try:
                validate_control_targets(DesignControls(attention_priority=brief.attention_priority), TemplateLoader().instantiate(brief.poster_type, brief))
            except ValueError as error:
                raise PosterPilotError(str(error), code="invalid_attention_priority", status_code=422) from error
        if brief.references:
            try:
                CaseRepository().resolve_selections(brief.references)
            except (ValueError, FileNotFoundError) as error:
                raise PosterPilotError(str(error), code="invalid_case_selection", status_code=422) from error
        record = self.repository.create(brief)
        artifact = self.artifacts.write_json(record.id, "brief.json", brief.model_dump(mode="json"))
        record = self.repository.add_artifact(record.id, artifact)
        self._emit(record.id, "run_created", "任务已创建，等待执行。")
        return record

    async def execute(self, run_id: UUID) -> RunRecord:
        record = self.require(run_id)
        if self.executor is None:
            return record
        claimed = self.repository.transition_status(
            run_id,
            expected="queued",
            status="running",
            current_node="agent",
        )
        if claimed is None:
            return self.require(run_id)
        self._emit(run_id, "node_started", "Agent 闭环开始执行。", node="agent")
        try:
            outcome = await self.executor.start(
                record.brief,
                run_id=run_id,
                run_directory=self.artifacts.run_directory(run_id),
            )
            return self._handle_outcome(run_id, outcome)
        except Exception as error:
            return self._fail_execution(
                run_id,
                error,
                node="agent",
                code="agent_execution_failed",
            )

    def begin_decision(
        self,
        run_id: UUID,
        decision: HumanDecision,
        *,
        expected_round_number: int,
    ) -> RunRecord:
        record = self.require(run_id)
        checkpoint = self.pending(run_id)
        if checkpoint.round_number != expected_round_number:
            raise PosterPilotError(
                "The reviewed round is stale. Reload the latest poster before deciding.",
                code="stale_human_decision",
                status_code=409,
            )
        if self.executor is None:
            raise PosterPilotError(
                "Agent executor is unavailable.",
                code="executor_unavailable",
                status_code=503,
            )
        if decision.controls is not None and decision.controls.has_request and checkpoint.layout is None:
            raise PosterPilotError("旧检查点缺少结构化布局，不能应用新控制；可以继续原有文字反馈流程。", code="design_controls_unavailable", status_code=409)
        if decision.controls is not None and checkpoint.layout is not None:
            try:
                validate_control_targets(decision.controls, PosterLayout.model_validate(checkpoint.layout))
                if decision.controls.selected_candidate_id:
                    selected = next((item for item in checkpoint.layout_candidates if item.id == decision.controls.selected_candidate_id), None)
                    if selected is None or not selected.selectable or selected.round_number != checkpoint.round_number:
                        raise DesignConstraintError("所选排版候选不存在或已过期，请刷新后重新选择")
                    assert_design_constraints(PosterLayout.model_validate(checkpoint.layout), selected.layout, decision.controls)
                    if checkpoint.analysis:
                        assert_rendered_locks(checkpoint.analysis, selected.analysis, decision.controls)
            except (DesignConstraintError, ValueError) as error:
                raise PosterPilotError(str(error), code="invalid_design_controls", status_code=422) from error
        running = self.repository.transition_status(
            run_id,
            expected="waiting_for_human",
            status="running",
            current_node="human_decision",
            expected_updated_at=record.updated_at,
        )
        if running is None:
            raise PosterPilotError(
                "Run is not waiting for human input.",
                code="run_not_waiting_for_human",
                status_code=409,
            )
        self._emit(
            run_id,
            "human_input_received",
            "已收到用户决策，继续执行 Agent。",
            node="human_decision",
            payload=decision.model_dump(mode="json"),
        )
        return running

    async def resume(self, run_id: UUID, decision: HumanDecision) -> RunRecord:
        record = self.require(run_id)
        if self.executor is None:
            return record
        try:
            outcome = await self.executor.resume(
                run_id,
                decision,
                run_directory=self.artifacts.run_directory(run_id),
            )
            return self._handle_outcome(run_id, outcome)
        except Exception as error:
            return self._fail_execution(
                run_id,
                error,
                node="react_agent",
                code="agent_resume_failed",
            )

    def _fail_execution(
        self,
        run_id: UUID,
        error: Exception,
        *,
        node: str,
        code: str,
    ) -> RunRecord:
        logger.error("Run execution or persistence failed: %s", run_id, exc_info=True)
        # If the database itself remains unavailable, propagate the failure. We cannot
        # truthfully return a persisted failed state; crash reconciliation is separate.
        failed = self.repository.update_status(
            run_id,
            "failed",
            current_node=node,
            error_code=code,
            error_message=str(error),
        )
        self._emit(run_id, "run_failed", "任务执行或结果保存失败。", node=node)
        return failed

    def pending(self, run_id: UUID) -> HumanCheckpoint:
        record = self.require(run_id)
        if record.status != "waiting_for_human":
            raise PosterPilotError(
                "Run is not waiting for human input.",
                code="run_not_waiting_for_human",
                status_code=409,
            )
        path = self.artifacts.run_directory(run_id) / "pending_human.json"
        if not path.is_file():
            raise PosterPilotError(
                "Pending human checkpoint was not found.",
                code="pending_checkpoint_not_found",
                status_code=404,
            )
        return HumanCheckpoint.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def get(self, run_id: UUID) -> RunRecord:
        return self.require(run_id)

    def list(self, *, limit: int = 50) -> list[RunRecord]:
        return self.repository.list(limit=limit)

    def artifact_path(self, run_id: UUID, name: str) -> Path:
        if not SAFE_ARTIFACT_NAME.fullmatch(name):
            raise ValueError("artifact name must be a plain safe filename")
        record = self.require(run_id)
        if name not in {artifact.name for artifact in record.artifacts}:
            raise FileNotFoundError(name)
        return self.artifacts.run_directory(run_id) / name

    def events(self, run_id: UUID) -> list[RunEvent]:
        self.require(run_id)
        path = self.artifacts.run_directory(run_id) / "events.jsonl"
        if not path.is_file():
            return []
        return [
            RunEvent.model_validate(json.loads(line))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _emit(
        self,
        run_id: UUID,
        event_type: str,
        message: str,
        *,
        node: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        event = RunEvent(
            run_id=run_id,
            type=event_type,
            node=node,
            message=message,
            payload=payload or {},
        )
        # Events are a best-effort projection. A damaged trace file must not strand
        # a claimed task or undo an already committed result. The database is truth.
        try:
            self.artifacts.append_event(event)
        except Exception:
            logger.exception("Could not persist event %s for run %s", event_type, run_id)
        try:
            self.event_bus.publish_nowait(event)
        except Exception:
            logger.exception("Could not publish event %s for run %s", event_type, run_id)

    def _register_generated_artifacts(self, run_id: UUID) -> None:
        for artifact in self.artifacts.list_run_artifacts(run_id):
            if artifact.name != "events.jsonl":
                self._add_artifact_if_missing(run_id, artifact)

    def _handle_outcome(
        self,
        run_id: UUID,
        outcome: AgentExecutionOutcome,
    ) -> RunRecord:
        self._emit_agent_events(run_id, outcome.events)
        self._register_generated_artifacts(run_id)
        if outcome.status == "waiting_for_human":
            checkpoint = outcome.checkpoint
            if checkpoint is None:  # pragma: no cover - schema enforces this.
                raise RuntimeError("Waiting outcome did not include a checkpoint.")
            artifact = self.artifacts.write_json(
                run_id,
                "pending_human.json",
                checkpoint.model_dump(mode="json"),
            )
            self._add_artifact_if_missing(run_id, artifact)
            waiting = self.repository.update_status(
                run_id,
                "waiting_for_human",
                current_node="human_review",
            )
            self._emit(
                run_id,
                "human_input_required",
                "评测已完成，等待用户决定下一步。",
                node="human_review",
                payload=checkpoint.model_dump(mode="json"),
            )
            return waiting

        result = outcome.result
        if result is None:  # pragma: no cover - schema enforces this.
            raise RuntimeError("Completed outcome did not include a result.")
        artifact = self.artifacts.write_json(run_id, "result.json", result)
        self._add_artifact_if_missing(run_id, artifact)
        self._register_generated_artifacts(run_id)
        completed = self.repository.update_status(run_id, "completed", current_node="finalize")
        self._emit(run_id, "node_completed", "Agent 闭环执行完成。", node="finalize")
        self._emit(run_id, "run_completed", "任务已完成。", node="finalize")
        return completed

    def _emit_agent_events(self, run_id: UUID, events: list[dict[str, Any]]) -> None:
        tool_nodes = {
            "search_design_knowledge",
            "search_poster_cases",
            "modify_typography",
            "modify_layout",
            "modify_visual",
            "adjust_background",
        }
        for item in events:
            node = str(item.get("node") or "agent")
            message = str(item.get("message") or "Agent 节点已完成。")
            payload = item.get("payload")
            safe_payload = payload if isinstance(payload, dict) else {}
            if node == "react_decide":
                event_type = "agent_decision"
            elif node in tool_nodes:
                self._emit(
                    run_id,
                    "tool_started",
                    f"Agent 调用工具：{node}",
                    node=node,
                    payload=safe_payload,
                )
                event_type = "tool_completed"
            elif node == "complete_round":
                event_type = "round_completed"
            else:
                event_type = "node_completed"
            self._emit(
                run_id,
                event_type,
                message,
                node=node,
                payload=safe_payload,
            )

    def _add_artifact_if_missing(self, run_id: UUID, artifact) -> None:
        record = self.require(run_id)
        if artifact.name not in {existing.name for existing in record.artifacts}:
            self.repository.add_artifact(run_id, artifact)

    def require(self, run_id: UUID) -> RunRecord:
        record = self.repository.get(run_id)
        if record is None:
            raise RunNotFoundError(run_id)
        return record
