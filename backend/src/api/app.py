"""HTTP assembly from application capabilities; no concrete infrastructure imports."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.types import Lifespan

from api.errors import APIError, error_response, handle_api_error, handle_validation_error
from api.health.routes import router as health_router
from api.identity.routes import router as identity_router
from api.middleware import request_boundary
from api.platform.routes import router as platform_router
from api.schemas import ErrorResponse
from developer_platform.application.errors import CatalogForbidden
from developer_platform.domain import DomainError
from identity.application.errors import CredentialDeliveryError, IdentityUnavailable
from identity.domain.errors import AuthenticationRejected, IdentityValidationError


def create_api(*, lifespan: Lifespan[FastAPI] | None = None) -> FastAPI:
    app = FastAPI(
        title="DevOps Hub API",
        version="0.1.0",
        description="Phase 1 foundation. Resource provisioning routes are not implemented yet.",
        lifespan=lifespan,
        responses={
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )
    app.middleware("http")(request_boundary)
    app.add_exception_handler(APIError, handle_api_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, handle_validation_error)  # type: ignore[arg-type]

    @app.exception_handler(AuthenticationRejected)
    async def unauthenticated(request: Request, exc: AuthenticationRejected) -> JSONResponse:
        return error_response(request, 401, exc.code, exc.message)

    @app.exception_handler(CatalogForbidden)
    async def forbidden(request: Request, exc: CatalogForbidden) -> JSONResponse:
        return error_response(request, 403, exc.code, exc.message)

    @app.exception_handler(IdentityUnavailable)
    async def unavailable(request: Request, exc: IdentityUnavailable) -> JSONResponse:
        return error_response(request, 503, exc.code, exc.message)

    @app.exception_handler(IdentityValidationError)
    async def identity_invalid(request: Request, exc: IdentityValidationError) -> JSONResponse:
        return error_response(request, 422, exc.code, exc.message)

    @app.exception_handler(CredentialDeliveryError)
    async def delivery_failed(request: Request, exc: CredentialDeliveryError) -> JSONResponse:
        return error_response(request, 500, exc.code, "Credential delivery failed")

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return error_response(request, 422, exc.code, exc.message)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return error_response(
            request, exc.status_code, "http_error", "Request could not be completed"
        )

    app.include_router(health_router)
    app.include_router(identity_router)
    app.include_router(platform_router)
    return app
