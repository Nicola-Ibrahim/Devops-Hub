"""Application-layer capability names.

Legacy import aliases keep existing adapters and downstream integrations working while
they migrate to the clearer capability paths.
"""

import importlib.abc
import importlib.util
import sys

_ALIASES = {
    "application_delivery": "workload_delivery",
    "application_delivery.attach_resource": "workload_delivery.attach_database",
    "application_delivery.create_application": "workload_delivery.create_workload",
    "application_delivery.deploy_application": "workload_delivery.deploy_workload",
    "application_delivery.process_preview_webhook": "workload_delivery.handle_preview_webhook",
    "application_delivery.read_applications": "workload_delivery.read_workloads",
    "project_registration": "projects",
    "resource_requests": "database_provisioning",
    "resource_lifecycle": "database_lifecycle",
    "resource_worker": "workers.resource_operations",
    "application_delivery.shared.ports": "workload_delivery.shared.ports",
    "application_delivery.shared.models": "workload_delivery.shared.models",
    "application_delivery.shared.database_binding": "workload_delivery.shared.database_binding",
    "application_delivery.shared.policy": "workload_delivery.shared.policy",
    "resource_lifecycle.ports": "database_lifecycle.ports",
    "resource_worker.handler": "workers.resource_operations.handler",
}


class _LegacyCapabilityLoader(importlib.abc.Loader):
    def __init__(self, target: str) -> None:
        self.target = target

    def create_module(self, spec):  # type: ignore[no-untyped-def]
        return importlib.import_module(f"{__name__}.{self.target}")

    def exec_module(self, module):  # type: ignore[no-untyped-def]
        return None


class _LegacyCapabilityFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):  # type: ignore[no-untyped-def]
        prefix = f"{__name__}."
        if not fullname.startswith(prefix):
            return None
        current = _ALIASES.get(fullname.removeprefix(prefix))
        if current is None:
            return None
        return importlib.util.spec_from_loader(fullname, _LegacyCapabilityLoader(current))


sys.meta_path.insert(0, _LegacyCapabilityFinder())
