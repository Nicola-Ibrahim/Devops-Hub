"""Read the optional database reference without putting credentials in environment or logs."""

import os
from pathlib import Path

import psycopg


def check_database() -> None:
    reference = os.environ.get("DATABASE_URL_FILE")
    if reference is None:
        return
    path = Path(reference)
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("Database configuration must be a private regular file")
    if not path.is_file():
        raise ValueError("Database configuration must be a private regular file")
    with path.open() as source:
        connection_string = source.read(4097).strip()
    if not connection_string or len(connection_string) > 4096:
        raise ValueError("Database configuration is invalid")
    with psycopg.connect(connection_string, connect_timeout=2) as connection:
        if connection.execute("SELECT 1").fetchone() != (1,):
            raise ValueError("Database readiness failed")
