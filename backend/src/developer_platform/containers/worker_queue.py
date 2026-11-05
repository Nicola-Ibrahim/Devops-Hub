"""Compatibility imports for the platform worker persistence adapters."""

from developer_platform.infra.persistence.worker_queue import (
    PostgresResourceEffectGuard as PostgresResourceEffectGuard,
)
from developer_platform.infra.persistence.worker_queue import (
    SqlAlchemyProvisioningQueue as SqlAlchemyProvisioningQueue,
)
