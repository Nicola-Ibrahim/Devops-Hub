"""Alembic migration environment; invoked only by explicit Alembic commands."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection, make_url

from migrations.metadata import registered_metadata
from shared.infra.settings import DatabaseSettings

config = context.config
if config.config_file_name is not None and config.file_config.has_section("formatters"):
    fileConfig(config.config_file_name)

target_metadata = registered_metadata()


def _database_settings() -> DatabaseSettings:
    injected = config.attributes.get("database_settings")
    if injected is not None:
        if not isinstance(injected, DatabaseSettings):
            raise TypeError("database_settings must be a DatabaseSettings instance")
        return injected
    return DatabaseSettings()


def _database_url() -> str:
    return _database_settings().database_url.get_secret_value()


def run_migrations_offline() -> None:
    context.configure(
        url=make_url(_database_url()),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_with_connection(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        _run_with_connection(supplied_connection)
        return

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        hide_parameters=True,
    )
    try:
        with connectable.connect() as connection:
            _run_with_connection(connection)
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
