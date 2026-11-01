"""HTTP authentication/access mapping; DI supplies ready application capabilities."""

from typing import Annotated, Literal, Protocol

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.identity.schemas import PrincipalView
from developer_platform.application.dto import AccessContext

ReadinessStatus = Literal["ready", "schema_not_ready", "database_unavailable"]


class ReadinessProbe(Protocol):
    async def inspect(self) -> ReadinessStatus: ...


class ReadCurrentIdentity(Protocol):
    async def execute(self, token: str | None) -> PrincipalView: ...


bearer = HTTPBearer(auto_error=False)


@inject
async def current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    authenticate: FromDishka[ReadCurrentIdentity],
) -> PrincipalView:
    return await authenticate.execute(credentials.credentials if credentials else None)


async def platform_access(
    principal: Annotated[PrincipalView, Depends(current_principal)],
) -> AccessContext:
    return AccessContext(
        principal.user_id, principal.project_id, principal.role, frozenset(principal.scopes)
    )
