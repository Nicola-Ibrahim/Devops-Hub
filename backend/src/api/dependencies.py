"""HTTP authentication/access mapping; DI supplies ready application capabilities."""

from typing import Annotated, Protocol

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import Depends

from api.credentials import RequestIdentity, request_identity
from api.identity.schemas import PrincipalView
from developer_platform.application.shared.dto import AccessContext


class ReadCurrentIdentity(Protocol):
    async def execute(self, token: RequestIdentity) -> PrincipalView: ...


@inject
async def current_principal(
    credentials: Annotated[RequestIdentity, Depends(request_identity)],
    authenticate: FromDishka[ReadCurrentIdentity],
) -> PrincipalView:
    return await authenticate.execute(credentials)


async def platform_access(
    principal: Annotated[PrincipalView, Depends(current_principal)],
) -> AccessContext:
    return AccessContext(
        principal.user_id, principal.project_id, principal.role, frozenset(principal.scopes)
    )
