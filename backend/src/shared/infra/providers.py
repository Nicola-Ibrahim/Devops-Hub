"""Shared PostgreSQL engine, session and transaction providers."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from shared.infra.clock import Clock
from shared.infra.persistence.database import create_async_database_engine
from shared.infra.persistence.unit_of_work import SqlAlchemyUnitOfWork
from shared.infra.readiness import ReadinessProbe, SqlAlchemyReadinessProbe
from shared.infra.settings import SCHEMA_REVISION, Settings


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


class RuntimeClockProvider(Provider):
    @provide(scope=Scope.APP)
    def clock(self) -> Clock:
        return lambda: datetime.now(UTC)
