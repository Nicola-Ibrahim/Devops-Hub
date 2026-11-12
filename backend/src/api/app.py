"""FastAPI application, error mapping, routing and configured app factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.exceptions import HTTPException
from starlette.types import Lifespan

from api.core.errors import APIError, error_response, handle_api_error, handle_validation_error
from api.core.middlewares.request_boundary import request_boundary
from api.core.schemas import ErrorResponse
from api.router import router as api_router
from api.settings.config import APISettings, get_api_settings
from composition.runtime import BackendRuntime
from devops_platform.application.shared.errors import CatalogForbidden, PlatformRequestError
from devops_platform.domain import DomainError
from identity.application.shared.errors import CredentialDeliveryError, IdentityUnavailable
from identity.domain.errors import AuthenticationRejected, IdentityValidationError
from shared.infra.settings import Settings


class DevOpsHubAPI(FastAPI):
    """Configured HTTP application, independent of concrete infrastructure wiring."""

    def __init__(
        self,
        settings: APISettings | None = None,
        *,
        lifespan: Lifespan[FastAPI] | None = None,
    ) -> None:
        settings = settings or get_api_settings()
        super().__init__(
            title=settings.title,
            version=settings.version,
            description=settings.description,
            openapi_url=settings.openapi_url,
            docs_url=settings.docs_url,
            redoc_url=settings.redoc_url,
            lifespan=lifespan,
            responses={
                404: {"model": ErrorResponse},
                409: {"model": ErrorResponse},
                401: {"model": ErrorResponse},
                403: {"model": ErrorResponse},
                422: {"model": ErrorResponse},
                503: {"model": ErrorResponse},
            },
        )
        app = self
        app.middleware("http")(request_boundary)
        app.add_exception_handler(APIError, handle_api_error)  # type: ignore[arg-type]
        app.add_exception_handler(RequestValidationError, handle_validation_error)  # type: ignore[arg-type]

        @app.exception_handler(AuthenticationRejected)
        async def unauthenticated(request: Request, exc: AuthenticationRejected) -> JSONResponse:
            return error_response(request, 401, exc.code, exc.message)

        @app.exception_handler(PlatformRequestError)
        async def platform_error(request: Request, exc: PlatformRequestError) -> JSONResponse:
            return error_response(request, exc.status, exc.code, exc.message)

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

        app.include_router(api_router)


def create_app(
    settings: Settings | None = None,
    *,
    engine: AsyncEngine | None = None,
    container: AsyncContainer | None = None,
    api_settings: APISettings | None = None,
) -> FastAPI:
    """Build the HTTP app and its process composition; injected resources stay caller-owned."""
    runtime = BackendRuntime(
        settings,
        engine=engine,
        container=container,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        try:
            await runtime.start()
            yield
        finally:
            await runtime.close()

    app = DevOpsHubAPI(api_settings, lifespan=lifespan)
    setup_dishka(runtime.container, app)
    return app
