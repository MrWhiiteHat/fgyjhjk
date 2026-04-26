"""Centralized exception middleware converting errors to safe JSON responses."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.backend.config import get_settings
from app.backend.core.exceptions import AppBaseError
from app.backend.schemas.errors import ErrorDetail, ErrorResponse
from app.backend.utils.logger import configure_logger


class ExceptionMiddleware(BaseHTTPMiddleware):
    """Map custom and unexpected exceptions into consistent error schema."""

    def __init__(self, app) -> None:
        super().__init__(app)
        settings = get_settings()
        self.settings = settings
        self.logger = configure_logger("backend.exceptions", settings.LOG_LEVEL, f"{settings.OUTPUT_DIR}/logs")

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except AppBaseError as exc:
            request_id = str(getattr(request.state, "request_id", "unknown-request"))
            payload = ErrorResponse(
                success=False,
                request_id=request_id,
                timestamp=datetime.now(timezone.utc),
                error_code=exc.error_code,
                message=exc.message,
                details=exc.details,
                errors=[ErrorDetail(error_code=exc.error_code, message=exc.message, details=exc.details)],
            )
            self.logger.warning("Handled app error request_id=%s code=%s message=%s", request_id, exc.error_code, exc.message)
            return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))
        except Exception as exc:  # noqa: BLE001
            request_id = str(getattr(request.state, "request_id", "unknown-request"))
            message = "Internal server error"
            details = {"hint": "Check server logs for traceback"} if self.settings.APP_ENV == "production" else {"cause": str(exc)}
            payload = ErrorResponse(
                success=False,
                request_id=request_id,
                timestamp=datetime.now(timezone.utc),
                error_code="INTERNAL_SERVER_ERROR",
                message=message,
                details=details,
                errors=[ErrorDetail(error_code="INTERNAL_SERVER_ERROR", message=message, details=details)],
            )
            self.logger.exception("Unhandled exception request_id=%s", request_id)
            return JSONResponse(status_code=500, content=payload.model_dump(mode="json"))
