"""Database completion only; repositories and domain policies belong to contexts."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")
R = TypeVar("R")


class DatabaseUnavailable(Exception):
    """Sanitized technical failure, translated by the owning host adapter."""


class SqlAlchemyUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.committed = False
        self._used = False

    async def run(self, action: Callable[[], Awaitable[T]], materialize: Callable[[T], R]) -> R:
        if self._used:
            raise RuntimeError("A unit of work executes one operation; enter a new scope.")
        self._used = True
        primary: BaseException | None = None
        try:
            await self.session.begin()
            value = materialize(await action())
            await self.session.commit()
            self.committed = True
            return value
        except BaseException as error:
            primary = DatabaseUnavailable() if isinstance(error, SQLAlchemyError) else error
            try:
                await asyncio.wait_for(self.session.rollback(), timeout=3)
            except BaseException:
                primary.add_note("Database rollback failed; the original failure was preserved.")
            if primary is not error:
                raise primary from error
            raise
        finally:
            try:
                await asyncio.wait_for(self.session.close(), timeout=3)
            except BaseException as error:
                if primary is not None:
                    primary.add_note(
                        "Database session cleanup failed; the original failure was preserved."
                    )
                elif isinstance(error, SQLAlchemyError):
                    raise DatabaseUnavailable() from error
                else:
                    raise
