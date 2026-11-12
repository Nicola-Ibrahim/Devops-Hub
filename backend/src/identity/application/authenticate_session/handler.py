from collections.abc import Callable
from datetime import datetime

from identity.application.authenticate_session.query import AuthenticateSessionQuery
from identity.domain.browser_errors import BrowserAuthenticationRejected
from identity.domain.interfaces.session_repository import SessionRepository
from identity.domain.records import SessionPrincipal


class AuthenticateSessionHandler:
    def __init__(
        self,
        repository: SessionRepository,
        clock: Callable[[], datetime],
        digest_secret: Callable[[str], str],
    ) -> None:
        self.repository = repository
        self.clock = clock
        self.digest_secret = digest_secret

    async def execute(self, query: AuthenticateSessionQuery) -> SessionPrincipal:
        result = await self.repository.authenticate_session(
            token_digest=self.digest_secret(query.session_token),
            project_id=query.project_id,
            now=self.clock(),
        )
        if result is None:
            raise BrowserAuthenticationRejected()
        return result[0]
