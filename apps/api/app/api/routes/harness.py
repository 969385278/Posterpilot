from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Request

from app.schemas.tool_release import GapTriageRequest, ToolReviewRequest

router = APIRouter(prefix="/datahub/harness", tags=["PosterHub tool governance"])


def _service(request: Request):
    return request.app.state.run_service.harness


@router.get("/tools")
def tools(request: Request):
    return _service(request).catalog()


@router.post("/tools/{name}/validate", status_code=202)
def validate(name: str, request: Request, background_tasks: BackgroundTasks):
    service = _service(request)
    report = service.start_validation(name)
    background_tasks.add_task(service.run_validation, report["id"])
    return report


@router.post("/tools/{name}/review")
def review(name: str, body: ToolReviewRequest, request: Request):
    return _service(request).review(name, body)


@router.get("/reports")
def reports(request: Request):
    return _service(request).reports()


@router.get("/reports/{report_id}")
def report(report_id: UUID, request: Request):
    return _service(request).report(report_id)


@router.post("/reports/{report_id}/cancel")
def cancel(report_id: UUID, request: Request):
    return _service(request).cancel_validation(report_id)


@router.post("/collect")
def collect(request: Request):
    return request.app.state.run_service.collect_failure_evidence()


@router.get("/gaps")
def gaps(request: Request):
    return _service(request).gaps()


@router.post("/gaps/{gap_id}/triage")
def triage(gap_id: str, body: GapTriageRequest, request: Request):
    return _service(request).triage(gap_id, body)
