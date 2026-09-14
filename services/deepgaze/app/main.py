from fastapi import FastAPI

from app.api import build_router
from app.cache import PredictionCache
from app.model import DeepGazeModel, SaliencyModel


def create_app(model: SaliencyModel | None = None) -> FastAPI:
    app = FastAPI(title="PosterPilot DeepGaze", version="0.1.0")
    predictor = model or DeepGazeModel()
    app.include_router(build_router(model=predictor, cache=PredictionCache()))

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "posterpilot-deepgaze"}

    return app


app = create_app()
