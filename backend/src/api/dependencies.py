"""HTTP authentication/access mapping; DI supplies ready application capabilities."""

from typing import Annotated, Literal, cast

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import Depends

from api.credentials import BrowserRequestCredentials, RequestIdentity, request_identity
from api.identity.schemas import PrincipalView
from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.errors import PlatformRequestError
from identity.application.authenticate_api_token.query import (
    AuthenticateApiTokenQuery,
)
from identity.application.authenticate_session.query import AuthenticateSessionQuery
from identity.application.module import IdentityModule


@inject
async def current_principal(
    credentials: Annotated[RequestIdentity, Depends(request_identity)],
    identity: FromDishka[IdentityModule],
) -> PrincipalView:
    if isinstance(credentials, BrowserRequestCredentials):
        principal = await identity.query(
            AuthenticateSessionQuery(credentials.session_token, credentials.project_id)
        )
        if principal.project_id is None or principal.role not in {"developer", "admin"}:
            raise PlatformRequestError("project_required", "Select an authorized project", 409)
        return PrincipalView(
            user_id=principal.user_id,
            project_id=principal.project_id,
            role=cast(Literal["developer", "admin"], principal.role),
            scopes=list(principal.scopes),
        )
    token_principal = await identity.query(AuthenticateApiTokenQuery(credentials))
    return PrincipalView(
        user_id=token_principal.user_id,
        project_id=token_principal.project_id,
        role=token_principal.role,
        scopes=sorted(token_principal.scopes),
    )


async def platform_access(
    principal: Annotated[PrincipalView, Depends(current_principal)],
) -> AccessContext:
    return AccessContext(
        principal.user_id, principal.project_id, principal.role, frozenset(principal.scopes)
    )
