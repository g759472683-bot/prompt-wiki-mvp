from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from . import models  # noqa: F401  (register tables on Base.metadata)
from .config import Settings
from .db import build_engine, build_sessionmaker
from .llm.client import DeepSeekClient
from .models import ensure_schema
from .routers import (
    ask,
    auth,
    compile,
    consistency,
    documents,
    feedback,
    health,
    jobs,
    packs,
    pins,
    releases,
    runs,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.ensure_dirs()

    engine = build_engine(settings.db_url)
    ensure_schema(engine)

    app = FastAPI(title="Prompt Wiki API", version="0.1.0")
    app.state.settings = settings
    app.state.engine = engine
    session_factory = build_sessionmaker(engine)
    app.state.sessionmaker = session_factory
    with session_factory() as session:
        auth.adopt_legacy_workspace(session, settings)
    app.state.llm = (
        DeepSeekClient(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
        if settings.deepseek_api_key
        else None
    )

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router, prefix="/v1")
    app.include_router(documents.router, prefix="/v1")
    app.include_router(documents.sources_router, prefix="/v1")
    app.include_router(compile.router, prefix="/v1")
    app.include_router(jobs.router, prefix="/v1")
    app.include_router(runs.router, prefix="/v1")
    app.include_router(packs.router, prefix="/v1")
    app.include_router(ask.router, prefix="/v1")
    app.include_router(releases.router, prefix="/v1")
    app.include_router(consistency.router, prefix="/v1")
    app.include_router(pins.router, prefix="/v1")
    app.include_router(feedback.router, prefix="/v1")

    static_dir = Path(__file__).parent / "static"

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/admin")

    @app.get("/admin", include_in_schema=False)
    def admin() -> FileResponse:
        return FileResponse(static_dir / "admin.html")

    return app
