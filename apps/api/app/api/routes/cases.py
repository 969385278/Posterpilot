from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.rag.case_repository import CaseRepository
from app.schemas.poster_case import PosterCase

router = APIRouter(tags=["poster-cases"])


@router.get("/poster-cases", response_model=list[PosterCase])
def list_poster_cases(q: str = Query(default="", max_length=200), style: str = Query(default="", max_length=80)):
    return CaseRepository().list_cases(query=q, style=style)


@router.get("/poster-cases/{case_id}", response_model=PosterCase)
def get_poster_case(case_id: str):
    try:
        return CaseRepository().get(case_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/poster-cases/{case_id}/image")
def get_poster_case_image(case_id: str):
    try:
        return FileResponse(CaseRepository().image_path(case_id))
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=404, detail="案例图片不存在。") from error
