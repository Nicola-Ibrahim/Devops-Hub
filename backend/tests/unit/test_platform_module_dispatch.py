"""The platform contract has one explicit and resolvable binding per message."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from developer_platform.authorization import ACTION_PERMISSIONS
from developer_platform.infra.composition.module import PLATFORM_HANDLER_REGISTRY
from infra.composition.factory import create_container
from shared.infra.settings import Settings


def test_every_platform_message_is_registered_once() -> None:
    registered = set(PLATFORM_HANDLER_REGISTRY.commands) | set(PLATFORM_HANDLER_REGISTRY.queries)
    assert set(ACTION_PERMISSIONS) == registered
    assert all(
        message.__module__ != "developer_platform.application.module" for message in registered
    )


def test_every_platform_handler_resolves_in_operation_scope_without_database_io() -> None:
    config = Settings(
        database_url="postgresql+psycopg://localhost:1/devops_hub_test", token_pepper="t" * 40
    )

    async def verify() -> None:
        container = create_container(config)
        try:
            async with container() as scope:
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
