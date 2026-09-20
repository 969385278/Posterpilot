from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.schemas.datahub import EditCaseRequest, ExperienceQuery, HubCase, ReviewCaseRequest

router = APIRouter(prefix="/datahub", tags=["PosterHub"])


def _service(request: Request):
    return request.app.state.run_service.datahub


@router.get("/cases", response_model=list[HubCase])
def list_cases(
    request: Request,
    status: Literal["candidate", "approved", "rejected", "withdrawn"] | None = None,
    run_id: UUID | None = None,
):
    return _service(request).repository.list(status=status, run_id=run_id)


@router.post("/capture/{run_id}", response_model=list[HubCase])
def capture(run_id: UUID, request: Request):
    runs = request.app.state.run_service
    return _service(request).capture(runs, run_id, origin=runs.data_origin)


@router.get("/stats")
def stats(request: Request):
    return _service(request).stats()


@router.post("/retrieve")
def retrieve(query: ExperienceQuery, request: Request):
    matches = _service(request).retrieve(query)
    return {
        "matches": matches,
        "method": "reviewed_text_bigrams",
        "note": "仅返回审核后的相关参考，不代表已执行或已改善效果。",
    }


@router.get("/cases/{case_id}", response_model=HubCase)
def get_case(case_id: UUID, request: Request):
    return _service(request).repository.get(case_id)


@router.get("/cases/{case_id}/quality")
def quality(case_id: UUID, request: Request):
    service = _service(request)
    case = service.repository.get(case_id)
    return {"issues": service.quality_issues(case), "revision": case.revision}


@router.put("/cases/{case_id}", response_model=HubCase)
def edit(case_id: UUID, body: EditCaseRequest, request: Request):
    return _service(request).edit(case_id, body)


@router.post("/cases/{case_id}/review", response_model=HubCase)
def review(case_id: UUID, body: ReviewCaseRequest, request: Request):
    return _service(request).review(case_id, body)


@router.get("/cases/{case_id}/image")
def image(case_id: UUID, request: Request, before: bool = False):
    return FileResponse(
        _service(request).image_path(case_id, before=before), media_type="image/png"
    )
