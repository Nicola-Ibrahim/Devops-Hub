"""Public dispatch contract for identity commands and queries."""

from typing import Protocol, TypeVar

from shared.dispatch import Command, Query

ResultT = TypeVar("ResultT")


class IdentityModule(Protocol):
    async def execute(self, command: Command[ResultT]) -> ResultT: ...

    async def query(self, query: Query[ResultT]) -> ResultT: ...
