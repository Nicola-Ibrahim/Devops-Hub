from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(
        status_code=status,
        content={"code": code, "message": message, "request_id": request.state.request_id},
        headers=headers,
    )


async def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
    return error_response(request, exc.status, exc.code, exc.message)


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Pydantic's default errors can echo input, including a submitted secret.
    return error_response(request, 422, "invalid_request", "Request validation failed")
