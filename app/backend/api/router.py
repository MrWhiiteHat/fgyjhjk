"""Top-level API router registration for all route groups."""

from __future__ import annotations

from fastapi import APIRouter

from app.backend.api.routes import admin, explain, health, predict_folder, predict_image, predict_video, predict_webcam_stub, report_generate, reports

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(predict_image.router)
api_router.include_router(predict_folder.router)
api_router.include_router(predict_video.router)
api_router.include_router(predict_webcam_stub.router)
api_router.include_router(explain.router)
api_router.include_router(reports.router)
api_router.include_router(report_generate.router)
api_router.include_router(admin.router)
