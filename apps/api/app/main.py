from contextlib import asynccontextmanager, nullcontext

from fastapi import FastAPI

from app.agent.runtime import create_runtime_executor
from app.api.routes.runs import router as runs_router
from app.api.routes.cases import router as cases_router
from app.api.routes.fonts import router as fonts_router
from app.api.routes.datahub import router as datahub_router
from app.api.routes.assistant import router as assistant_router
from app.api.routes.memory import router as memory_router
from app.api.routes.intent import router as intent_router
from app.api.routes.decisions import router as decisions_router
from app.api.routes.harness import router as harness_router
from app.api.routes.visual_assets import router as visual_assets_router
from app.providers.embedding.asset_ollama import AssetOllamaEmbeddings
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.persistence.run_repository import RunRepository
from app.persistence.runtime_ownership import runtime_ownership
from app.services.artifact_service import ArtifactService
from app.services.event_bus import EventBus
from app.services.run_service import RunService
from app.services.intent_router import IntentRouter


def create_app(run_service: RunService | None = None) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ownership = nullcontext(False) if run_service else runtime_ownership(settings.database_url)
        with ownership as exclusive:
            service = run_service or _build_run_service(settings)
            app.state.run_service = service
            try:
                if exclusive:
                    service.reconcile_interrupted_runs()
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
    app.include_router(assistant_router, prefix="/api/v1")
    app.include_router(memory_router, prefix="/api/v1")
    app.include_router(intent_router, prefix="/api/v1")
    app.include_router(decisions_router, prefix="/api/v1")
    app.include_router(harness_router, prefix="/api/v1")
    app.include_router(visual_assets_router, prefix="/api/v1")
    return app


def _build_run_service(settings) -> RunService:
    service = RunService(
        repository=RunRepository(settings.database_url),
        artifacts=ArtifactService(settings.data_dir / "runs"),
        event_bus=EventBus(),
        executor=create_runtime_executor(settings),
        asset_embeddings=AssetOllamaEmbeddings(
            model=settings.ollama_embedding_model, base_url=settings.ollama_base_url,
            timeout_seconds=min(settings.embedding_timeout_seconds, 15),
        ),
        asset_embedding_id=f"ollama:{settings.ollama_base_url}:{settings.ollama_embedding_model}",
    )

    service.intent_router = IntentRouter(
        service, direct_llm=settings.intent_routing_mode == "deepseek",
    )
    return service


app = create_app()
