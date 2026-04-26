"""Optional integration helper for app backend main module."""

from __future__ import annotations

from fastapi import FastAPI

from cloud.backend_extension.router import cloud_router


def include_cloud_module(app: FastAPI) -> None:
    """Attach cloud router to existing FastAPI application."""

    app.include_router(cloud_router)
