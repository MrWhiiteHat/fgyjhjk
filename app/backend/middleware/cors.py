"""CORS middleware registration utility."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.backend.config import get_settings


def configure_cors(app: FastAPI) -> None:
    """Attach CORS middleware using environment-driven configuration."""
    settings = get_settings()
    if not bool(settings.ENABLE_CORS):
        return

    origins = settings.CORS_ORIGINS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
