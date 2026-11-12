"""FastAPI application, error mapping, routing and configured app factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.exceptions import HTTPException
from starlette.types import Lifespan

from api.errors import APIError, error_response, handle_api_error, handle_validation_error
from api.health.metrics import router as metrics_router
from api.health.routes import router as health_router
from api.identity.browser import router as browser_router
from api.identity.routes import router as identity_router
from api.middleware import request_boundary
from api.platform.applications import router as applications_router
from api.platform.routes import router as platform_router
from api.schemas import ErrorResponse
from composition.factory import create_container
from developer_platform.application.shared.errors import CatalogForbidden, PlatformRequestError
from developer_platform.domain import DomainError
from identity.application.shared.errors import CredentialDeliveryError, IdentityUnavailable
from identity.domain.errors import AuthenticationRejected, IdentityValidationError
from shared.infra.settings import Settings


@dataclass(frozen=True)
class APIConfiguration:
    """HTTP metadata and documentation routes; deployment secrets stay in Settings."""

    title: str = "DevOps Hub API"
    version: str = "0.1.0"
    description: str = (
        "Developer platform API for identity, projects, approved resources, "
        "application templates, and durable delivery workflows."
    )
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"


class DevOpsHubAPI(FastAPI):
    """Configured HTTP application, independent of concrete infrastructure wiring."""

    def __init__(
        self,
        config: APIConfiguration | None = None,
        *,
        lifespan: Lifespan[FastAPI] | None = None,
    ) -> None:
        config = config or APIConfiguration()
        super().__init__(
            title=config.title,
            version=config.version,
            description=config.description,
            docs_url=config.docs_url,
            redoc_url=config.redoc_url,
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

        app.include_router(health_router)
        app.include_router(metrics_router)

        app.include_router(browser_router)
        app.include_router(identity_router)
        app.include_router(platform_router)
        app.include_router(applications_router)


def create_app(
    settings: Settings | None = None,
    *,
    engine: AsyncEngine | None = None,
    container: AsyncContainer | None = None,
    api_config: APIConfiguration | None = None,
) -> FastAPI:
    """Build the HTTP app and its process composition; injected resources stay caller-owned."""
    runtime = (
        container
        if container is not None
        else create_container(
            settings if settings is not None else Settings(),  # type: ignore[call-arg]
            engine=engine,
        )
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if container is None:
                await runtime.close()

    app = DevOpsHubAPI(api_config, lifespan=lifespan)
    setup_dishka(runtime, app)
    return app
