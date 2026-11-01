from collections.abc import Callable
from datetime import datetime

from identity.application.ports import AuthenticationReader, TokenHasher
from identity.contracts import AuthenticatedPrincipal
from identity.domain.credentials import authenticate_snapshot
from identity.domain.errors import AuthenticationRejected


class Authenticate:
    def __init__(
        self, reader: AuthenticationReader, hasher: TokenHasher, clock: Callable[[], datetime]
    ) -> None:
        self.reader = reader
        self.hasher = hasher
        self.clock = clock

    def execute(self, token: str | None) -> AuthenticatedPrincipal:
        if token is None or not 32 <= len(token) <= 256:
            raise AuthenticationRejected()
        snapshot = self.reader.find_by_digest(self.hasher.digest(token))
        return authenticate_snapshot(snapshot, self.clock())
