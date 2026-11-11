"""The platform contract has one explicit and resolvable binding per message."""

import asyncio
import inspect

from sqlalchemy.ext.asyncio import AsyncSession

import developer_platform.application.module as messages
from containers.factory import create_container
from developer_platform.containers.module import PLATFORM_HANDLER_REGISTRY
from shared.dispatch import Command, Query
from shared.infra.settings import Settings


def test_every_platform_message_is_registered_once() -> None:
    declared = {
        cls
        for _, cls in inspect.getmembers(messages, inspect.isclass)
        if cls.__module__ == messages.__name__ and issubclass(cls, (Command, Query))
    }
    registered = set(PLATFORM_HANDLER_REGISTRY.commands) | set(PLATFORM_HANDLER_REGISTRY.queries)
    assert declared == registered


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
