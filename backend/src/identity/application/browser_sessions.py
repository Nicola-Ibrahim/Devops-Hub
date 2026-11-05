"""Browser session use cases for internal identity."""

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from uuid import UUID

from identity.domain.browser_errors import BrowserAuthenticationRejected
from identity.domain.browser_identity import (
    BrowserIdentityRepository,
    BrowserPrincipal,
    BrowserSession,
)

Clock = Callable[[], datetime]
DigestSecret = Callable[[str], str]
GenerateSecret = Callable[[], str]


def require_browser_origin(origin: str | None, allowed_origins: tuple[str, ...]) -> None:
    allowed = {value.rstrip("/") for value in allowed_origins}
    if origin is None or origin.rstrip("/") not in allowed:
        raise BrowserAuthenticationRejected()


class BrowserSessionService:
    """Application actions for login sessions; the caller owns the DB transaction."""

    def __init__(
        self,
        repository: BrowserIdentityRepository,
        clock: Clock,
        digest_secret: DigestSecret,
        generate_secret: GenerateSecret,
        allowed_origins: tuple[str, ...],
    ) -> None:
        self.repository = repository
        self.clock = clock
        self.digest_secret = digest_secret
        self.generate_secret = generate_secret
        self.allowed_origins = frozenset(origin.rstrip("/") for origin in allowed_origins)

    def _check_origin(self, origin: str | None) -> None:
        require_browser_origin(origin, tuple(self.allowed_origins))

    async def authorize_mutation(
        self, token: str, csrf: str, origin: str | None
    ) -> BrowserPrincipal:
        self._check_origin(origin)
        principal = await self.repository.authorize_browser_operation(
            self.digest_secret(token), None, self.clock(), lock_for_mutation=True
        )
        if principal is None or not await self.repository.validate_csrf(
            self.digest_secret(token), self.digest_secret(csrf)
        ):
            raise BrowserAuthenticationRejected()
        return principal

    async def authenticate(self, session_token: str, project_id: UUID | None) -> BrowserPrincipal:
        result = await self.repository.authenticate_session(
            token_digest=self.digest_secret(session_token),
            project_id=project_id,
            now=self.clock(),
        )
        if result is None:
            raise BrowserAuthenticationRejected()
        return result[0]

    async def current(self, session_token: str) -> BrowserPrincipal:
        csrf = self.generate_secret()
        result = await self.repository.authenticate_session(
            token_digest=self.digest_secret(session_token), project_id=None, now=self.clock()
        )
        if result is None or not await self.repository.rotate_csrf(
            self.digest_secret(session_token), self.digest_secret(csrf), self.clock()
        ):
            raise BrowserAuthenticationRejected()
        return replace(result[0], csrf_token=csrf)

    async def select_project(
        self, session_token: str, project_id: UUID, csrf_token: str, origin: str | None
    ) -> BrowserPrincipal:
        await self.authorize_mutation(session_token, csrf_token, origin)
        csrf = self.generate_secret()
        principal = await self.repository.select_project(
            token_digest=self.digest_secret(session_token),
            project_id=project_id,
            now=self.clock(),
        )
        if principal is None or not await self.repository.rotate_csrf(
            self.digest_secret(session_token), self.digest_secret(csrf), self.clock()
        ):
            raise BrowserAuthenticationRejected()
        return replace(principal, csrf_token=csrf)

    async def logout(self, session_token: str, csrf_token: str, origin: str | None) -> None:
        await self.authorize_mutation(session_token, csrf_token, origin)
        await self.repository.logout(self.digest_secret(session_token), self.clock())

    async def logout_all(self, session_token: str, csrf_token: str, origin: str | None) -> int:
        principal = await self.authorize_mutation(session_token, csrf_token, origin)
        return await self.repository.logout_all(principal.user_id, self.clock())

    async def list_sessions(self, session_token: str) -> tuple[BrowserSession, ...]:
        principal = await self.authenticate(session_token, None)
        return await self.repository.list_sessions(
            principal.user_id, principal.session_id, self.clock()
        )

    async def revoke_session(
        self, session_token: str, session_id: UUID, csrf_token: str, origin: str | None
    ) -> bool:
        principal = await self.authorize_mutation(session_token, csrf_token, origin)
        return await self.repository.revoke_session(principal.user_id, session_id, self.clock())
