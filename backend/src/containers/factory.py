"""Small composition entrypoint: register providers rather than assemble service graphs."""

import asyncio

from dishka import AsyncContainer, Provider, Scope, from_context, make_async_container
from dishka.integrations.fastapi import FastapiProvider
from sqlalchemy.ext.asyncio import AsyncEngine

from containers.providers import (
    DatabaseProvider,
    ExternalDatabase,
    IdentityProvider,
    PlatformProvider,
)
from entrypoints.schema import registered_metadata
from entrypoints.settings import Settings


class RuntimeContext(Provider):
    settings = from_context(Settings, scope=Scope.APP)
    database = from_context(ExternalDatabase, scope=Scope.APP)


def create_container(
    settings: Settings, *, engine: AsyncEngine | None = None, overrides: tuple[Provider, ...] = ()
) -> AsyncContainer:
    registered_metadata()
    return make_async_container(
        RuntimeContext(),
        DatabaseProvider(),
        IdentityProvider(),
        PlatformProvider(),
        FastapiProvider(),
        *overrides,
        context={Settings: settings, ExternalDatabase: ExternalDatabase(engine)},
        lock_factory=asyncio.Lock,
    )
