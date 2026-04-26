"""Security headers middleware utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class SecurityHeadersConfig:
    """Security header configuration options."""

    enabled: bool = True
    cache_control: str = "no-store"
    content_security_policy: str = "default-src 'self'"


def default_security_headers(config: SecurityHeadersConfig | None = None) -> Dict[str, str]:
    cfg = config or SecurityHeadersConfig()
    if not cfg.enabled:
        return {}

    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Cache-Control": cfg.cache_control,
        "Content-Security-Policy": cfg.content_security_policy,
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }


def apply_security_headers(response, config: SecurityHeadersConfig | None = None):
    """Attach secure response headers to a response object."""
    headers = default_security_headers(config=config)
    for key, value in headers.items():
        response.headers[key] = value
    return response


try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request

    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        """Middleware to apply security headers on all responses."""

        def __init__(self, app, config: SecurityHeadersConfig | None = None) -> None:
            super().__init__(app)
            self.config = config or SecurityHeadersConfig()

        async def dispatch(self, request: Request, call_next):
            response = await call_next(request)
            return apply_security_headers(response, config=self.config)

except Exception:  # noqa: BLE001
    SecurityHeadersMiddleware = object  # type: ignore[assignment]


def add_security_headers_middleware(app, enabled: bool = True, cache_control: str = "no-store"):
    """FastAPI/Starlette helper to register security-header middleware."""
    if not enabled:
        return app
    app.add_middleware(SecurityHeadersMiddleware, config=SecurityHeadersConfig(enabled=True, cache_control=cache_control))
    return app
