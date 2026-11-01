"""Declarative bindings; this is the only layer selecting concrete implementations."""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from api.dependencies import ReadCurrentIdentity, ReadinessProbe
from containers.operations import (
    CurrentIdentityQuery,
    IssueApiTokenToFile,
    RevokeApiTokenCommand,
)
from developer_platform.application.catalog import ReadCatalog
from developer_platform.application.permissions import ALL_SCOPES
from entrypoints.settings import SCHEMA_REVISION, Settings
from identity.application.authenticate import AuthenticateApiToken
from identity.application.issue_token import IssueApiToken
from identity.application.ports import ApiTokenRepository, TokenGenerator, TokenHasher
from identity.application.revoke_token import RevokeApiToken
from identity.infra.persistence.store import SQLAlchemyApiTokenRepository
from identity.infra.tokens import PepperedTokenHasher, SecureTokenGenerator
from shared.infra.persistence.database import create_async_database_engine
from shared.infra.persistence.unit_of_work import SqlAlchemyUnitOfWork
from shared.infra.readiness import SqlAlchemyReadinessProbe

Clock = Callable[[], datetime]


@dataclass(frozen=True)
class ExternalDatabase:
    engine: AsyncEngine | None = None


class DatabaseProvider(Provider):
    @provide(scope=Scope.APP)
    async def engine(
        self, settings: Settings, external: ExternalDatabase
    ) -> AsyncIterator[AsyncEngine]:
        engine = external.engine or create_async_database_engine(
            settings.database_url.get_secret_value(), settings.database_connect_timeout
        )
        try:
            yield engine
        finally:
            if external.engine is None:
                await engine.dispose()

    @provide(scope=Scope.APP)
    def sessions(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False)

    @provide(scope=Scope.REQUEST)
    def session(self, sessions: async_sessionmaker[AsyncSession]) -> AsyncSession:
        # The outer UoW closes this session before returning, not after HTTP emission.
        return sessions()

    unit = provide(SqlAlchemyUnitOfWork, scope=Scope.REQUEST)

    @provide(scope=Scope.APP)
    def readiness(self, engine: AsyncEngine) -> ReadinessProbe:
        return SqlAlchemyReadinessProbe(engine, SCHEMA_REVISION)


class IdentityProvider(Provider):
    @provide(scope=Scope.APP)
    def clock(self) -> Clock:
        return lambda: datetime.now(UTC)

    @provide(scope=Scope.APP)
    def hasher(self, settings: Settings) -> TokenHasher:
        return PepperedTokenHasher(settings.token_pepper.get_secret_value())

    @provide(scope=Scope.APP)
    def generator(self) -> TokenGenerator:
        return SecureTokenGenerator()

    repository = provide(
        SQLAlchemyApiTokenRepository, provides=ApiTokenRepository, scope=Scope.REQUEST
    )
    authenticate = provide(AuthenticateApiToken, scope=Scope.REQUEST)
    revoke = provide(RevokeApiToken, scope=Scope.REQUEST)
    revoke_command = provide(RevokeApiTokenCommand, scope=Scope.REQUEST)
    issue_command = provide(IssueApiTokenToFile, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST)
    def issue(
        self,
        repository: ApiTokenRepository,
        hasher: TokenHasher,
        generator: TokenGenerator,
        clock: Clock,
    ) -> IssueApiToken:
        return IssueApiToken(repository, hasher, generator, clock, ALL_SCOPES, ALL_SCOPES)

    current_identity = provide(
        CurrentIdentityQuery, provides=ReadCurrentIdentity, scope=Scope.REQUEST
    )


class PlatformProvider(Provider):
    catalog = provide(ReadCatalog, scope=Scope.REQUEST)
