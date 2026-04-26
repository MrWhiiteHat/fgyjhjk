"""Request ID middleware assigning traceable IDs per request."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.backend.constants import REQUEST_ID_HEADER
from app.backend.utils.helpers import generate_request_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject request ID into request.state and response headers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER, generate_request_id())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
