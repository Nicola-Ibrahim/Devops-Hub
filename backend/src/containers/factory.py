"""Small composition entrypoint: register providers rather than assemble service graphs."""

import asyncio

from dishka import AsyncContainer, Provider, Scope, from_context, make_async_container
from dishka.integrations.fastapi import FastapiProvider
from sqlalchemy.ext.asyncio import AsyncEngine

from containers.http_providers import HttpCompositionProvider
from containers.schema import registered_metadata
from developer_platform.application.permissions import ALL_SCOPES
from developer_platform.containers.providers import ApplicationDeliveryProvider, PlatformProvider
from identity.containers.providers import IdentityProvider, IdentityTokenScopePolicy
from shared.infra.providers import DatabaseProvider, ExternalDatabase, RuntimeClockProvider
from shared.infra.settings import Settings


class RuntimeContext(Provider):
    settings = from_context(Settings, scope=Scope.APP)
    database = from_context(ExternalDatabase, scope=Scope.APP)
    identity_token_scopes = from_context(IdentityTokenScopePolicy, scope=Scope.APP)


def create_container(
    settings: Settings, *, engine: AsyncEngine | None = None, overrides: tuple[Provider, ...] = ()
) -> AsyncContainer:
    registered_metadata()
    return make_async_container(
        RuntimeContext(),
        HttpCompositionProvider(),
        DatabaseProvider(),
        RuntimeClockProvider(),
        IdentityProvider(),
        PlatformProvider(),
        ApplicationDeliveryProvider(),
        FastapiProvider(),
        *overrides,
        context={
            Settings: settings,
            ExternalDatabase: ExternalDatabase(engine),
            IdentityTokenScopePolicy: IdentityTokenScopePolicy(tuple(ALL_SCOPES)),
        },
        lock_factory=asyncio.Lock,
    )
