"""Short independent transaction for bearer authentication."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from identity.application.authenticate_api_token.handler import AuthenticateApiTokenHandler
from identity.application.authenticate_api_token.query import AuthenticateApiTokenQuery
from identity.application.shared.errors import IdentityUnavailable
from identity.application.shared.ports import TokenHasher
from identity.contracts import AuthenticatedPrincipal
from identity.infra.persistence.store import SQLAlchemyApiTokenRepository
from shared.infra.clock import Clock
from shared.infra.persistence.unit_of_work import DatabaseUnavailable, SqlAlchemyUnitOfWork


class TokenAuthenticationHost:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        hasher: TokenHasher,
        clock: Clock,
    ) -> None:
        self.sessions = sessions
        self.hasher = hasher
        self.clock = clock

    async def authenticate(self, token: str | None) -> AuthenticatedPrincipal:
        try:
            async with self.sessions() as session:
                unit = SqlAlchemyUnitOfWork(session)
                handler = AuthenticateApiTokenHandler(
                    SQLAlchemyApiTokenRepository(session), self.hasher, self.clock
                )
                return await unit.run(
                    lambda: handler.execute(AuthenticateApiTokenQuery(token)),
                    lambda principal: principal,
                )
        except DatabaseUnavailable as error:
            raise IdentityUnavailable() from error
