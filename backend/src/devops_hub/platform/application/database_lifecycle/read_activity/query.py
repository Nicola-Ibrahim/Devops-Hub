from dataclasses import dataclass
from uuid import UUID

from devops_hub.platform.application.shared.resource_repository import ResourceActivity
from devops_hub.platform.domain.access import AccessContext
from shared.dispatch import Query


@dataclass(frozen=True, slots=True)
class ReadResourceActivity(Query[tuple[ResourceActivity, ...]]):
    access: AccessContext
    project_id: UUID
