from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.schemas.visual_asset import AssetEdit, AssetEnrich, AssetReview, AssetSearch, AssetUpload

router = APIRouter(prefix="/datahub/visual-assets", tags=["PosterHub visual assets"])


def service(request):
    return request.app.state.run_service.visual_assets


@router.get("")
def list_assets(request: Request):
    return service(request).list()


@router.post("", status_code=201)
def upload_asset(body: AssetUpload, request: Request):
    return service(request).upload(body.image_base64, body.metadata, body.source)


@router.post("/search")
def search_assets(body: AssetSearch, request: Request):
    return service(request).search(body)


@router.post("/index")
def index_assets(request: Request):
    return service(request).index()


@router.get("/{asset_id}/image")
def image(asset_id: UUID, request: Request):
    return FileResponse(service(request).image_path(asset_id), media_type="image/png")


@router.post("/{asset_id}/edit")
def edit(asset_id: UUID, body: AssetEdit, request: Request):
    return service(request).edit(asset_id, body)


@router.post("/{asset_id}/review")
def review(asset_id: UUID, body: AssetReview, request: Request):
    return service(request).review(asset_id, body)


@router.post("/{asset_id}/enrich")
async def enrich(asset_id: UUID, body: AssetEnrich, request: Request):
    executor = request.app.state.run_service.executor
    provider = getattr(
        getattr(getattr(executor, "evaluation", None), "vision", None), "provider", None
    )
    return await service(request).enrich(asset_id, body.expected_revision, provider)
