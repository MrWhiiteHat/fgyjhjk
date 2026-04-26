"""FastAPI application entrypoint for Module 5 backend API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.backend.api.router import api_router
from app.backend.config import get_settings
from app.backend.constants import API_V1_PREFIX, APP_VERSION
from app.backend.core.shutdown import shutdown_event
from app.backend.core.startup import startup_event
from app.backend.middleware.cors import configure_cors
from app.backend.middleware.exception_middleware import ExceptionMiddleware
from app.backend.middleware.logging_middleware import LoggingMiddleware
from app.backend.middleware.request_id import RequestIDMiddleware

try:
    from ops.security.security_headers import add_security_headers_middleware
except Exception:  # noqa: BLE001
    add_security_headers_middleware = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Execute startup and shutdown hooks in modern FastAPI lifecycle."""
    startup_event(app)
    try:
        yield
    finally:
        shutdown_event(app)


def create_app() -> FastAPI:
    """Create and configure FastAPI app with middleware, routes, and lifecycle hooks."""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=APP_VERSION,
        debug=bool(settings.DEBUG),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(ExceptionMiddleware)
    app.add_middleware(LoggingMiddleware)
    if add_security_headers_middleware is not None:
        add_security_headers_middleware(app, enabled=True)
    configure_cors(app)
    artifacts_root = Path(settings.OUTPUT_DIR)
    artifacts_root.mkdir(parents=True, exist_ok=True)
    app.mount("/artifacts", StaticFiles(directory=str(artifacts_root), check_dir=False), name="artifacts")

    app.include_router(api_router, prefix=API_V1_PREFIX)

    @app.get("/")
    def root() -> dict:
        return {
            "app": settings.APP_NAME,
            "version": APP_VERSION,
            "status": "running",
            "docs": "/docs",
            "api_prefix": API_V1_PREFIX,
        }

    return app


app = create_app()
