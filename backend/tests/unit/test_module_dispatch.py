"""Contract checks for explicit, lazy context module registration."""

import asyncio

import pytest

from shared.dispatch import (
    Command,
    HandlerRegistry,
    ModuleDispatcher,
    Query,
    RegistrationError,
    UnsupportedMessage,
)


class ChangeName(Command[str]):
    pass


class ReadName(Query[str]):
    pass


class ChangeNameHandler:
    async def execute(self, message: ChangeName) -> str:
        return "changed"


class ReadNameHandler:
    async def execute(self, message: ReadName) -> str:
        return "read"


def test_registry_rejects_duplicates_wrong_kind_and_missing_messages() -> None:
    with pytest.raises(RegistrationError, match="more than one"):
        HandlerRegistry(commands=[(ChangeName, ChangeNameHandler)] * 2, queries=[])
    with pytest.raises(RegistrationError, match="wrong kind"):
        HandlerRegistry(commands=[(ReadName, ReadNameHandler)], queries=[])
    with pytest.raises(RegistrationError, match="required query"):
        HandlerRegistry(commands=[], queries=[], required_queries=[ReadName])


def test_dispatch_resolves_only_selected_handler_and_rejects_unknown() -> None:
    selected: list[type[object]] = []
    registry = HandlerRegistry(
        commands=[(ChangeName, ChangeNameHandler)], queries=[(ReadName, ReadNameHandler)]
    )

    async def resolve(handler: type[object]) -> object:
        selected.append(handler)
        return handler()

    module = ModuleDispatcher(registry, resolve)

    async def run() -> None:
        assert await module.execute(ChangeName()) == "changed"
        assert selected == [ChangeNameHandler]
        assert await module.query(ReadName()) == "read"
        assert selected == [ChangeNameHandler, ReadNameHandler]
        with pytest.raises(UnsupportedMessage, match="Unsupported command"):
            await ModuleDispatcher(HandlerRegistry(commands=[], queries=[]), resolve).execute(
                ChangeName()
            )

    asyncio.run(run())
