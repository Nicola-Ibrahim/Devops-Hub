"""Typed platform module contract; messages live beside their use cases."""

from typing import Protocol, TypeVar

from shared.dispatch import Command, Query

ResultT = TypeVar("ResultT")


class DeveloperPlatformModule(Protocol):
    async def execute(self, command: Command[ResultT]) -> ResultT: ...

    async def query(self, query: Query[ResultT]) -> ResultT: ...
