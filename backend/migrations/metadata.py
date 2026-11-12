"""Import every context model before Alembic reads aggregate metadata."""

from sqlalchemy import MetaData

from shared.infra.persistence.base import Base


def registered_metadata() -> MetaData:
    # Alembic owns metadata discovery; runtime processes never call this helper.
    from devops_platform.infra.persistence import delivery as delivery_models
    from devops_platform.infra.persistence import models as platform_models
    from identity.infra.persistence import models as identity_models
    from shared.infra.persistence import audit

    _ = (identity_models, platform_models, delivery_models, audit)
    return Base.metadata
