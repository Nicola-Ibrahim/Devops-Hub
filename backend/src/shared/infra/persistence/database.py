"""Technical engine construction; receives values rather than runtime settings."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_database_engine(database_url: str, connect_timeout: int = 3) -> Engine:
    return create_engine(
        database_url,
        connect_args={"connect_timeout": connect_timeout},
        pool_pre_ping=True,
        hide_parameters=True,
        echo=False,
    )


# Runtime applications use async sessions; Alembic intentionally retains the sync factory.
def create_async_database_engine(database_url: str, connect_timeout: int = 3) -> AsyncEngine:
    return create_async_engine(
        database_url,
        connect_args={"connect_timeout": connect_timeout},
        pool_pre_ping=True,
        hide_parameters=True,
        echo=False,
    )
