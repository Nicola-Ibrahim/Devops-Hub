"""Cold-process host wiring must not rely on migration/test import side effects."""

import inspect

from devops_hub.platform.infra.workers import resource_worker


def test_worker_does_not_register_migration_metadata_at_runtime():
    assert "registered_metadata" not in vars(resource_worker)
    assert "registered_metadata" not in inspect.getsource(resource_worker.run_worker)
