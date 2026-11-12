"""Technical engine construction; receives values rather than runtime settings."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_database_engine(
    database_url: str,
    connect_timeout: int = 3,
    *,
    pool_size: int = 5,
    max_overflow: int = 5,
    pool_timeout: int = 30,
    pool_recycle: int = 1800,
) -> Engine:
    return create_engine(
        database_url,
        connect_args={"connect_timeout": connect_timeout},
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        hide_parameters=True,
        echo=False,
    )


# Runtime applications use async sessions; Alembic intentionally retains the sync factory.
def create_async_database_engine(
    database_url: str,
    connect_timeout: int = 3,
    *,
    pool_size: int = 5,
    max_overflow: int = 5,
    pool_timeout: int = 30,
    pool_recycle: int = 1800,
) -> AsyncEngine:
    return create_async_engine(
        database_url,
        connect_args={"connect_timeout": connect_timeout},
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        hide_parameters=True,
        echo=False,
    )
