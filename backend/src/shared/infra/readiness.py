"""Database readiness without transport or business dependencies."""

from typing import Literal

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

ReadinessStatus = Literal["ready", "schema_not_ready", "database_unavailable"]


class SqlAlchemyReadinessProbe:
    def __init__(self, engine: AsyncEngine, revision: str) -> None:
        self.engine = engine
        self.revision = revision

    async def inspect(self) -> ReadinessStatus:
        try:
            async with self.engine.connect() as connection:
                revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        except SQLAlchemyError:
            return "database_unavailable"
        return "ready" if revision == self.revision else "schema_not_ready"
