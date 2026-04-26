"""Custom backend exceptions with HTTP status and error code mapping."""

from __future__ import annotations

from typing import Any, Dict, Optional


class AppBaseError(Exception):
    """Base exception carrying error code and HTTP status metadata."""

    status_code: int = 500
    error_code: str = "UNKNOWN_ERROR"

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(AppBaseError):
    status_code = 422
    error_code = "VALIDATION_ERROR"


class UnsupportedFileTypeError(AppBaseError):
    status_code = 415
    error_code = "UNSUPPORTED_FILE_TYPE"


class FileTooLargeError(AppBaseError):
    status_code = 413
    error_code = "FILE_TOO_LARGE"


class ModelNotLoadedError(AppBaseError):
    status_code = 503
    error_code = "MODEL_NOT_LOADED"


class InferenceError(AppBaseError):
    status_code = 500
    error_code = "INFERENCE_ERROR"


class ExplainabilityError(AppBaseError):
    status_code = 500
    error_code = "EXPLAINABILITY_ERROR"


class ReportNotFoundError(AppBaseError):
    status_code = 404
    error_code = "REPORT_NOT_FOUND"


class PostprocessNotFoundError(AppBaseError):
    status_code = 404
    error_code = "POSTPROCESS_NOT_FOUND"


class AuthError(AppBaseError):
    status_code = 401
    error_code = "AUTH_ERROR"


class RateLimitError(AppBaseError):
    status_code = 429
    error_code = "RATE_LIMIT_ERROR"
