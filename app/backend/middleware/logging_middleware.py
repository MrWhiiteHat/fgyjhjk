"""Structured request logging middleware with latency metrics."""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.backend.config import get_settings
from app.backend.core.telemetry import get_telemetry
from app.backend.utils.logger import configure_logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log method/path/status/duration and send telemetry updates."""

    def __init__(self, app) -> None:
        super().__init__(app)
        settings = get_settings()
        self.logger = configure_logger("backend.http", settings.LOG_LEVEL, f"{settings.OUTPUT_DIR}/logs")

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0

        request_id = str(getattr(request.state, "request_id", "unknown-request"))
        path = request.url.path
        status = int(response.status_code)

        self.logger.info(
            "request_id=%s method=%s path=%s status=%d duration_ms=%.2f",
            request_id,
            request.method,
            path,
            status,
            duration_ms,
        )

        get_telemetry().record(endpoint=path, status_code=status, duration_ms=duration_ms)

        ops_prometheus = getattr(request.app.state, "ops_prometheus", None)
        if ops_prometheus is not None:
            model_version = "unknown"
            model_service = getattr(request.app.state, "model_service", None)
            if model_service is not None:
                try:
                    model_version = str(model_service.get_model_info().get("model_version", "unknown"))
                except Exception:  # noqa: BLE001
                    model_version = "unknown"
            ops_prometheus.track_request(
                endpoint=path,
                status_code=status,
                model_version=model_version,
                latency_ms=duration_ms,
            )

        return response
