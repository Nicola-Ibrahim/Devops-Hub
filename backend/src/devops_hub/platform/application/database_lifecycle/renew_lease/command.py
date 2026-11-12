from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from devops_hub.platform.application.shared.resource_repository import ResourceSnapshot
from devops_hub.platform.domain.access import AccessContext
from shared.dispatch import Command


@dataclass(frozen=True, slots=True)
class RenewDatabase(Command[ResourceSnapshot]):
    access: AccessContext
    resource_id: UUID
    expected_revision: int
    expires_at: datetime
