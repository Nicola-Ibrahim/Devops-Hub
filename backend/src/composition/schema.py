"""Register every context explicitly before exposing complete migration metadata."""

from sqlalchemy import MetaData

from shared.infra.persistence.base import Base


def registered_metadata() -> MetaData:
    # Registration happens only at the outer composition/migration boundary.
    from developer_platform.infra.persistence import delivery as delivery_models
    from developer_platform.infra.persistence import models as platform_models
    from identity.infra.persistence import models as identity_models
    from shared.infra.persistence import audit

    _ = (identity_models, platform_models, delivery_models, audit)
    return Base.metadata
