from fastapi import APIRouter, Request

from app.schemas.intent import IntentRequest, IntentResolution
from app.services.intent_router import IntentRouter

router = APIRouter(tags=["intent-routing"])


@router.post("/intents/resolve", response_model=IntentResolution)
async def resolve(body: IntentRequest, request: Request):
    runs = request.app.state.run_service
    router_service = getattr(runs, "intent_router", None) or IntentRouter(runs)
    return await router_service.resolve(body)
