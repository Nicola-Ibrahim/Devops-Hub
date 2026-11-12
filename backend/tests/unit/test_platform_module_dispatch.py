"""The platform contract has one explicit and resolvable binding per message."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from composition.container import BackendContainer
from devops_hub.platform.application.database_lifecycle.read_activity.handler import (
    ListResourceActivityQueryHandler,
)
from devops_hub.platform.application.database_lifecycle.read_connection.handler import (
    GetDatabaseConnectionQueryHandler,
)
from devops_hub.platform.application.database_lifecycle.renew_lease.handler import (
    RenewDatabaseLeaseHandler,
)
from devops_hub.platform.application.database_provisioning.read_resources.handler import (
    ReadResourcesHandler,
)
from devops_hub.platform.application.database_provisioning.submit_database_request.handler import (
    RequestTemporaryDatabaseHandler,
)
from devops_hub.platform.application.shared.resource_repository import ResourceRepository
from devops_hub.platform.authorization import ACTION_PERMISSIONS
from devops_hub.platform.infra.composition.module import PLATFORM_HANDLER_REGISTRY
from shared.infra.settings import Settings


def test_every_platform_message_is_registered_once() -> None:
    registered = set(PLATFORM_HANDLER_REGISTRY.commands) | set(PLATFORM_HANDLER_REGISTRY.queries)
    assert set(ACTION_PERMISSIONS) == registered
    assert all(
        message.__module__ != "devops_hub.platform.application.module" for message in registered
    )


def test_every_platform_handler_resolves_in_operation_scope_without_database_io() -> None:
    config = Settings(
        database_url="postgresql+psycopg://localhost:1/devops_hub_test", token_pepper="t" * 40
    )

    async def verify() -> None:
        container = BackendContainer(config).combined()
        try:
            async with container() as scope:
                repository = await scope.get(ResourceRepository)
                for handler in (
                    RequestTemporaryDatabaseHandler,
                    RenewDatabaseLeaseHandler,
                    GetDatabaseConnectionQueryHandler,
                    ListResourceActivityQueryHandler,
                    ReadResourcesHandler,
                ):
                    assert (await scope.get(handler)).repository is repository
                handlers = (
                    *PLATFORM_HANDLER_REGISTRY.commands.values(),
                    *PLATFORM_HANDLER_REGISTRY.queries.values(),
                )
                for handler in handlers:
                    assert isinstance(await scope.get(handler), handler)
                await (await scope.get(AsyncSession)).close()
        finally:
            await container.close()

    asyncio.run(verify())
