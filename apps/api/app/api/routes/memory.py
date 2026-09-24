from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.schemas.memory import (
    MemoryEventInput,
    MemoryScope,
    RetractMemoryInput,
    SourceMessageInput,
)

router = APIRouter(prefix="/datahub/users/{user_id}", tags=["PosterHub memory"])


def _service(request: Request):
    return request.app.state.run_service.memory


@router.get("/profile")
def profile(user_id: str, request: Request, scope: MemoryScope = "all"):
    return _service(request).profile(user_id, scope=scope)


@router.get("/events")
def events(
    user_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=200),
    before: int | None = Query(None, ge=1),
):
    return _service(request).events(user_id, limit=limit, before=before)


@router.post("/sources")
def save_source(user_id: str, body: SourceMessageInput, request: Request):
    return _service(request).save_source(user_id, body)


@router.get("/sources/{source_id}")
def get_source(user_id: str, source_id: UUID, request: Request):
    return _service(request).source(user_id, source_id)


@router.post("/extract")
async def extract(user_id: str, body: SourceMessageInput, request: Request):
    provider = getattr(request.app.state.run_service.executor, "text_provider", None)
    return await _service(request).extract(user_id, body, provider)


@router.post("/events")
def record(user_id: str, body: MemoryEventInput, request: Request):
    return _service(request).record(user_id, body)


@router.post("/events/{event_id}/retract")
def retract(user_id: str, event_id: UUID, body: RetractMemoryInput, request: Request):
    return _service(request).retract(user_id, event_id, **body.model_dump())
