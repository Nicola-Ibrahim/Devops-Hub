"""Explicit migrations only; API startup never creates or upgrades tables."""

from alembic import context
from sqlalchemy import Connection

from migrations.metadata import registered_metadata
from shared.infra.persistence.database import create_database_engine
from shared.infra.settings import DatabaseSettings

config = context.config
target_metadata = registered_metadata()


def run_with_connection(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    settings = DatabaseSettings()  # type: ignore[call-arg]
    context.configure(
        url=settings.database_url.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
elif (connection := config.attributes.get("connection")) is not None:
    run_with_connection(connection)
else:
    settings = DatabaseSettings()  # type: ignore[call-arg]
    engine = create_database_engine(
        settings.database_url.get_secret_value(), settings.database_connect_timeout
    )
    try:
        with engine.connect() as connection:
            run_with_connection(connection)
    finally:
        engine.dispose()
