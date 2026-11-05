from collections.abc import Callable
from datetime import datetime

from identity.application.ports import TokenHasher
from identity.contracts import AuthenticatedPrincipal
from identity.domain.api_tokens import ApiTokenRepository
from identity.domain.credentials import authenticate_api_token_credentials
from identity.domain.errors import AuthenticationRejected


class AuthenticateApiToken:
    def __init__(
        self, repository: ApiTokenRepository, hasher: TokenHasher, clock: Callable[[], datetime]
    ) -> None:
        self.repository = repository
        self.hasher = hasher
        self.clock = clock

    async def execute(self, token: str | None) -> AuthenticatedPrincipal:
        if token is None or not 32 <= len(token) <= 256:
            raise AuthenticationRejected()
        snapshot = await self.repository.find_token_credential(self.hasher.digest(token))
        return authenticate_api_token_credentials(snapshot, self.clock())
