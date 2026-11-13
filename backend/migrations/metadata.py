"""Aggregate ORM metadata for Alembic schema operations."""

from sqlalchemy import MetaData

from devops_platform.infra.persistence import delivery as _delivery_models
from devops_platform.infra.persistence import models as _platform_models
from identity.infra.persistence import models as _identity_models
from shared.infra.persistence import audit as _audit_models
from shared.infra.persistence.base import Base


def registered_metadata() -> MetaData:
    """Import every mapping owner and return their shared metadata."""
    # Keep explicit references so imports remain intentional and discoverable.
    _ = (_audit_models, _identity_models, _platform_models, _delivery_models)
    return Base.metadata
