"""Small composition entrypoint: register providers rather than assemble service graphs."""

import asyncio

from dishka import AsyncContainer, Provider, Scope, from_context, make_async_container
from dishka.integrations.fastapi import FastapiProvider
from sqlalchemy.ext.asyncio import AsyncEngine

from api.composition.providers import ApiCompositionProvider
from composition.integrations.providers import CrossContextIntegrationProvider
from composition.schema import registered_metadata
from composition.worker_providers import ApplicationWorkerProvider
from developer_platform.authorization import ALL_SCOPES
from developer_platform.infra.composition.providers_delivery import ApplicationDeliveryProvider
from developer_platform.infra.composition.providers_platform import PlatformProvider
from identity.infra.composition.providers import IdentityProvider, IdentityTokenScopePolicy
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
        ApiCompositionProvider(),
        CrossContextIntegrationProvider(),
        DatabaseProvider(),
        RuntimeClockProvider(),
        IdentityProvider(),
        PlatformProvider(),
        ApplicationDeliveryProvider(),
        ApplicationWorkerProvider(),
        FastapiProvider(),
        *overrides,
        context={
            Settings: settings,
            ExternalDatabase: ExternalDatabase(engine),
            IdentityTokenScopePolicy: IdentityTokenScopePolicy(tuple(ALL_SCOPES)),
        },
        lock_factory=asyncio.Lock,
    )
