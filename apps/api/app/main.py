from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agent.runtime import create_runtime_executor
from app.api.routes.runs import router as runs_router
from app.api.routes.cases import router as cases_router
from app.api.routes.fonts import router as fonts_router
from app.api.routes.datahub import router as datahub_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.persistence.run_repository import RunRepository
from app.services.artifact_service import ArtifactService
from app.services.event_bus import EventBus
from app.services.run_service import RunService


def create_app(run_service: RunService | None = None) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        service = run_service or _build_run_service(settings)
        app.state.run_service = service
        try:
            yield
        finally:
            await service.aclose()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)
    # Injected services remain usable in TestClient calls that do not enter lifespan.
    app.state.run_service = run_service

    @app.get("/api/v1/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "posterpilot-api"}

    app.include_router(runs_router, prefix="/api/v1")
    app.include_router(cases_router, prefix="/api/v1")
    app.include_router(fonts_router, prefix="/api/v1")
    app.include_router(datahub_router, prefix="/api/v1")
    return app


def _build_run_service(settings) -> RunService:
    return RunService(
        repository=RunRepository(settings.database_url),
        artifacts=ArtifactService(settings.data_dir / "runs"),
        event_bus=EventBus(),
        executor=create_runtime_executor(settings),
    )


app = create_app()
