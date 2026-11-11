"""Typed messages and explicit, scope-local handler dispatch."""

from collections.abc import Awaitable, Callable, Iterable
from types import MappingProxyType
from typing import Any, Protocol, TypeVar, cast

ResultT = TypeVar("ResultT")
MessageT = TypeVar("MessageT", contravariant=True)
ReplyT = TypeVar("ReplyT", covariant=True)


class Command[ResultT]:
    """A state-changing request with a statically known result type."""


class Query[ResultT]:
    """A read request with a statically known result type."""


class Handler(Protocol[MessageT, ReplyT]):
    async def execute(self, message: MessageT) -> ReplyT: ...


class RegistrationError(ValueError):
    """The trusted application registration is incomplete or inconsistent."""


class UnsupportedMessage(TypeError):
    """A caller submitted a message not registered by its bounded context."""


class HandlerRegistry:
    def __init__(
        self,
        *,
        commands: Iterable[tuple[type[Command[Any]], type[Any]]],
        queries: Iterable[tuple[type[Query[Any]], type[Any]]],
        required_commands: Iterable[type[Command[Any]]] = (),
        required_queries: Iterable[type[Query[Any]]] = (),
    ) -> None:
        command_map = self._build(commands, Command)
        query_map = self._build(queries, Query)
        if set(required_commands) - command_map.keys():
            raise RegistrationError("A required command has no handler")
        if set(required_queries) - query_map.keys():
            raise RegistrationError("A required query has no handler")
        self.commands = MappingProxyType(command_map)
        self.queries = MappingProxyType(query_map)

    @staticmethod
    def _build(
        registrations: Iterable[tuple[type[Any], type[Any]]], marker: type[Any]
    ) -> dict[type[Any], type[Any]]:
        result: dict[type[Any], type[Any]] = {}
        for message, handler in registrations:
            if not isinstance(message, type) or not issubclass(message, marker):
                raise RegistrationError("A message is registered under the wrong kind")
            if message in result:
                raise RegistrationError("A message has more than one handler")
            if not isinstance(handler, type) or not callable(getattr(handler, "execute", None)):
                raise RegistrationError("A registered handler must define execute")
            result[message] = handler
        return result


class ModuleDispatcher:
    """Resolve only the selected handler from the active DI scope."""

    def __init__(
        self,
        registry: HandlerRegistry,
        resolve: Callable[[type[Any]], Awaitable[Any]],
    ) -> None:
        self._registry = registry
        self._resolve = resolve

    async def execute(self, command: Command[ResultT]) -> ResultT:
        handler_type = self._registry.commands.get(type(command))
        if handler_type is None:
            raise UnsupportedMessage("Unsupported command")
        handler = await self._resolve(handler_type)
        return cast(ResultT, await handler.execute(command))

    async def query(self, query: Query[ResultT]) -> ResultT:
        handler_type = self._registry.queries.get(type(query))
        if handler_type is None:
            raise UnsupportedMessage("Unsupported query")
        handler = await self._resolve(handler_type)
        return cast(ResultT, await handler.execute(query))
