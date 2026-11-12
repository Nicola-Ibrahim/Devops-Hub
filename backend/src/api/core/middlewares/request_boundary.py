from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from api.core.errors import error_response


async def request_boundary(request: Request, call_next: RequestResponseEndpoint) -> Response:
    request.state.request_id = str(uuid4())
    try:
        response = await call_next(request)
    except Exception:
        # Expected failures are mapped from application-owned exceptions in app.py.
        response = error_response(request, 500, "internal_error", "An internal error occurred")
    response.headers["X-Request-ID"] = request.state.request_id
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response
