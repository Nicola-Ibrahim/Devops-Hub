from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from identity.domain.browser_errors import BrowserAuthenticationRejected
from identity.domain.interfaces.session_repository import SessionRepository
from identity.domain.records import SessionPrincipal

Clock = Callable[[], datetime]
DigestSecret = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class AuthorizeBrowserMutationCommand:
    """Internal authorization input shared by protected session mutations."""

    session_token: str = field(repr=False)
    csrf_token: str = field(repr=False)
    origin: str | None


def require_browser_origin(origin: str | None, allowed_origins: tuple[str, ...]) -> None:
    allowed = {value.rstrip("/") for value in allowed_origins}
    if origin is None or origin.rstrip("/") not in allowed:
        raise BrowserAuthenticationRejected()


class AuthorizeBrowserMutationHandler:
    def __init__(
        self,
        repository: SessionRepository,
        clock: Clock,
        digest_secret: DigestSecret,
        allowed_origins: tuple[str, ...],
    ) -> None:
        self.repository = repository
        self.clock = clock
        self.digest_secret = digest_secret
        self.allowed_origins = allowed_origins

    async def execute(self, command: AuthorizeBrowserMutationCommand) -> SessionPrincipal:
        require_browser_origin(command.origin, self.allowed_origins)
        token_digest = self.digest_secret(command.session_token)
        principal = await self.repository.authorize_browser_operation(
            token_digest, None, self.clock(), lock_for_mutation=True
        )
        if principal is None or not await self.repository.validate_csrf(
            token_digest, self.digest_secret(command.csrf_token)
        ):
            raise BrowserAuthenticationRejected()
        return principal
