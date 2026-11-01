"""Technical engine construction; receives values rather than runtime settings."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_database_engine(database_url: str, connect_timeout: int = 3) -> Engine:
    return create_engine(
        database_url,
        connect_args={"connect_timeout": connect_timeout},
        pool_pre_ping=True,
        hide_parameters=True,
        echo=False,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
