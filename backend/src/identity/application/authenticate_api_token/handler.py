from collections.abc import Callable
from datetime import datetime

from identity.application.authenticate_api_token.query import AuthenticateApiTokenQuery
from identity.application.shared.ports import TokenHasher
from identity.contracts import AuthenticatedPrincipal
from identity.domain.api_tokens import ApiTokenRepository
from identity.domain.credentials import authenticate_api_token_credentials
from identity.domain.errors import AuthenticationRejected


class AuthenticateApiTokenHandler:
    def __init__(
        self, repository: ApiTokenRepository, hasher: TokenHasher, clock: Callable[[], datetime]
    ) -> None:
        self.repository = repository
        self.hasher = hasher
        self.clock = clock

    async def execute(self, query: AuthenticateApiTokenQuery) -> AuthenticatedPrincipal:
        token = query.token
        if token is None or not 32 <= len(token) <= 256:
            raise AuthenticationRejected()
        snapshot = await self.repository.find_token_credential(self.hasher.digest(token))
        identity = authenticate_api_token_credentials(snapshot, self.clock())
        return AuthenticatedPrincipal(
            user_id=identity.user_id,
            project_id=identity.project_id,
            token_id=identity.token_id,
            role=identity.role,
            scopes=identity.scopes,
        )
