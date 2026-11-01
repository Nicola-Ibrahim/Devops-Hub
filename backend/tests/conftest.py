"""PostgreSQL checks opt in to a disposable database, then isolate each test in a schema."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url


def migration_config(connection):
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


def validated_test_url(raw: str, environment: dict[str, str] | None = None) -> URL:
    """Validate the effective libpq destination, not just the URL authority."""
    environment = dict(os.environ) if environment is None else environment
    if any(environment.get(key) for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE")):
        raise ValueError("Connection environment overrides are not allowed for integration checks")
    url = make_url(raw)
    # Only a single host override is supported (needed for temporary Unix sockets).
    # Reject service, hostaddr, dbname, options and all other libpq URL overrides.
    if set(url.query) - {"host"}:
        raise ValueError("Connection query overrides are not allowed for integration checks")
    effective_host = url.query.get("host", url.host)
    local = isinstance(effective_host, str) and (
        effective_host in {"localhost", "127.0.0.1", "::1"}
        or (effective_host.startswith("/") and "," not in effective_host)
    )
    if (
        url.drivername != "postgresql+psycopg"
        or not (url.database or "").startswith("devops_hub_test")
        or not local
    ):
        raise ValueError("Integration checks require a local database named devops_hub_test*")
    return url


@pytest.fixture
def postgres_engine():
    raw = os.environ.get("PLATFORM_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("Set PLATFORM_TEST_DATABASE_URL to an isolated devops_hub_test database")
    try:
        url = validated_test_url(raw)
    except ValueError:
        pytest.fail(
            "Unsafe integration database configuration; use a local devops_hub_test database"
        )
    schema = "test_" + uuid4().hex
    admin = create_engine(url, hide_parameters=True)
    engine = create_engine(
        url, connect_args={"options": f"-csearch_path={schema}"}, hide_parameters=True
    )
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        with engine.begin() as connection:
            command.upgrade(migration_config(connection), "head")
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
