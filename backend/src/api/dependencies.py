"""HTTP-only dependency access. Sessions and concrete adapters never enter here."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from developer_platform.application.catalog import ReadCatalog
from developer_platform.application.dto import AccessContext
from identity.application.authenticate import Authenticate
from identity.contracts import AuthenticatedPrincipal

ReadinessStatus = Literal["ready", "schema_not_ready", "database_unavailable"]


@dataclass(frozen=True)
class ApiServices:
    authenticate: Authenticate
    catalog: ReadCatalog
    readiness: Callable[[], ReadinessStatus]


def get_services(request: Request) -> ApiServices:
    services: ApiServices = request.app.state.services
    return services


bearer = HTTPBearer(auto_error=False)


def current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    services: Annotated[ApiServices, Depends(get_services)],
) -> AuthenticatedPrincipal:
    return services.authenticate.execute(credentials.credentials if credentials else None)


def platform_access(
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
) -> AccessContext:
    # Map only the trusted authentication result, never request-body owner values.
    return AccessContext(principal.user_id, principal.project_id, principal.role, principal.scopes)
