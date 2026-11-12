"""Same-transaction cross-context authentication, at the composition boundary."""

from collections.abc import Callable
from datetime import datetime
from typing import Literal, cast

from sqlalchemy.ext.asyncio import AsyncSession

from api.credentials import BrowserRequestCredentials, RequestIdentity
from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.errors import PlatformRequestError
from identity.application.authenticate_api_token.handler import AuthenticateApiTokenHandler
from identity.application.authenticate_api_token.query import AuthenticateApiTokenQuery
from identity.infra.hosts.identity_sessions import authenticate_browser_operation
from identity.infra.persistence.store import SQLAlchemyApiTokenRepository
from identity.infra.security.tokens import PepperedTokenHasher
from shared.infra.settings import Settings


async def authenticate_request(
    session: AsyncSession,
    identity: RequestIdentity,
    settings: Settings,
    clock: Callable[[], datetime],
) -> AccessContext:
    if isinstance(identity, BrowserRequestCredentials):
        principal = await authenticate_browser_operation(
            session,
            identity.session_token,
            identity.project_id,
            clock,
            identity.csrf_token,
            identity.origin,
            settings.browser_allowed_origins,
            identity.mutate,
            settings.token_pepper.get_secret_value(),
        )
        if principal.project_id is None or principal.role not in {"developer", "admin"}:
            raise PlatformRequestError("project_required", "Select an authorized project", 409)
        return AccessContext(
            principal.user_id,
            principal.project_id,
            cast(Literal["developer", "admin"], principal.role),
            frozenset(principal.scopes),
        )
    principal_token = await AuthenticateApiTokenHandler(
        SQLAlchemyApiTokenRepository(session),
        PepperedTokenHasher(settings.token_pepper.get_secret_value()),
        clock,
    ).execute(AuthenticateApiTokenQuery(identity))
    return AccessContext(
        principal_token.user_id,
        principal_token.project_id,
        principal_token.role,
        principal_token.scopes,
    )
