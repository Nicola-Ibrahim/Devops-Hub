from dataclasses import dataclass
from uuid import UUID

from developer_platform.domain.access import AccessContext
from developer_platform.domain.resource_lifecycle_repository import ResourceActivity
from shared.dispatch import Query


@dataclass(frozen=True, slots=True)
class ReadResourceActivity(Query[tuple[ResourceActivity, ...]]):
    access: AccessContext
    project_id: UUID
