import asyncio
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from app.schemas.brief import PosterBrief
from app.schemas.react import HumanCheckpoint, HumanDecision, HumanDecisionRequest
from app.schemas.run import RunRecord
from app.services.run_service import RunService

router = APIRouter(tags=["runs"])


def _service(request: Request) -> RunService:
    return request.app.state.run_service


@router.post("/runs", response_model=RunRecord, status_code=202)
async def create_run(
    brief: PosterBrief,
    background_tasks: BackgroundTasks,
    request: Request,
) -> RunRecord:
    service = _service(request)
    record = service.create(brief)
    if service.can_execute:
        background_tasks.add_task(service.execute, record.id)
    return record


@router.get("/runs", response_model=list[RunRecord])
async def list_runs(request: Request, limit: int = 50) -> list[RunRecord]:
    return _service(request).list(limit=limit)


@router.get("/runs/{run_id}", response_model=RunRecord)
async def get_run(run_id: UUID, request: Request) -> RunRecord:
    return _service(request).get(run_id)


@router.get("/runs/{run_id}/pending", response_model=HumanCheckpoint)
async def get_pending_human_input(run_id: UUID, request: Request) -> HumanCheckpoint:
    return _service(request).pending(run_id)


@router.post("/runs/{run_id}/decisions", response_model=RunRecord, status_code=202)
async def submit_human_decision(
    run_id: UUID,
    decision: HumanDecisionRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> RunRecord:
    service = _service(request)
    agent_decision = HumanDecision(action=decision.action, instruction=decision.instruction, controls=decision.controls)
    record = service.begin_decision(
        run_id,
        agent_decision,
        expected_round_number=decision.expected_round_number,
    )
    background_tasks.add_task(service.resume, run_id, agent_decision)
    return record


@router.get("/runs/{run_id}/artifacts/{artifact_name}")
async def read_artifact(run_id: UUID, artifact_name: str, request: Request) -> FileResponse:
    try:
        path = _service(request).artifact_path(run_id, artifact_name)
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=404, detail="Artifact was not found.") from error
    return FileResponse(path)


@router.get("/runs/{run_id}/events")
async def stream_events(run_id: UUID, request: Request) -> StreamingResponse:
    service = _service(request)
    service.require(run_id)
    last_id = request.headers.get("last-event-id")

    async def event_stream():
        # Subscribe before reading history to close the replay/live race.
        queue = service.event_bus.subscribe(run_id)
        try:
            history = service.events(run_id)
            seen = {event.id for event in history}
            start = next((index + 1 for index, event in enumerate(history)
                          if str(event.id) == last_id), 0)
            for event in history[start:]:
                yield _serialize_event(event)
            while True:
                if queue.empty() and service.get(run_id).status in {
                    "waiting_for_human", "completed", "failed",
                }:
                    yield "event: stream_end\ndata: {}\n\n"
                    return
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if event.id in seen:
                    continue
                seen.add(event.id)
                yield _serialize_event(event)
                if event.type in {"human_input_required", "run_completed", "run_failed"}:
                    yield "event: stream_end\ndata: {}\n\n"
                    return
        finally:
            service.event_bus.unsubscribe(run_id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _serialize_event(event) -> str:
    return f"id: {event.id}\nevent: {event.type}\ndata: {event.model_dump_json()}\n\n"
