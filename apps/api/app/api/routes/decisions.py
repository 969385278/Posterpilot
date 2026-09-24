from uuid import UUID

from fastapi import APIRouter, Request

from app.schemas.datahub import ReviewCaseRequest
from app.schemas.decision import CreateDecisionCard, DecisionCard, EditDecisionCard

router = APIRouter(prefix="/datahub/decisions", tags=["PosterHub decisions"])


def _service(request: Request):
    return request.app.state.run_service.datahub.decisions


@router.get("", response_model=list[DecisionCard])
def list_cards(request: Request):
    return _service(request).repository.list()


@router.post("", response_model=DecisionCard)
def create(body: CreateDecisionCard, request: Request):
    return _service(request).create(body)


@router.get("/{card_id}", response_model=DecisionCard)
def get(card_id: UUID, request: Request):
    return _service(request).repository.get(card_id)


@router.put("/{card_id}", response_model=DecisionCard)
def edit(card_id: UUID, body: EditDecisionCard, request: Request):
    return _service(request).edit(card_id, body)


@router.post("/{card_id}/review", response_model=DecisionCard)
def review(card_id: UUID, body: ReviewCaseRequest, request: Request):
    return _service(request).review(card_id, body)


@router.get("/{card_id}/quality")
def quality(card_id: UUID, request: Request):
    service = _service(request)
    return {"issues": service.quality_issues(service.repository.get(card_id))}
