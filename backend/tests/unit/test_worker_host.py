"""Cold-process host wiring must not rely on migration/test import side effects."""

import subprocess
import sys


def test_worker_registers_all_foreign_key_targets_before_database_work():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import asyncio
import developer_platform.infra.workers.resource_worker as worker
from shared.infra.persistence.base import Base

def check_metadata(*args):
    names = {table.name for table in Base.metadata.sorted_tables}
    assert {"users", "projects", "resources", "application_delivery_steps"} <= names
    raise SystemExit(0)

worker.create_async_database_engine = check_metadata
settings = worker.Settings(database_url="postgresql+psycopg://localhost/devops_hub_test",
    token_pepper="synthetic-host-test-pepper-value-32bytes",
    installation_id="00000000-0000-0000-0000-000000000001",
    local_provider_enabled=True, resource_key="synthetic-unused-key")
asyncio.run(worker.run_worker(settings, once=True))
""",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
