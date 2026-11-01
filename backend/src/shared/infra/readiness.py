"""Database availability/schema inspection without HTTP or domain dependencies."""

from typing import Literal

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

ReadinessStatus = Literal["ready", "schema_not_ready", "database_unavailable"]


class SQLReadinessProbe:
    def __init__(self, engine: Engine, revision: str) -> None:
        self._engine = engine
        self._revision = revision

    def inspect(self) -> ReadinessStatus:
        try:
            with self._engine.connect() as connection:
                revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar()
        except SQLAlchemyError:
            return "database_unavailable"
        return "ready" if revision == self._revision else "schema_not_ready"
