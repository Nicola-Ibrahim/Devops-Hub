from dataclasses import dataclass
from uuid import UUID

from devops_platform.domain.access import AccessContext
from shared.dispatch import Command


@dataclass(frozen=True, slots=True)
class DeleteDatabase(Command[UUID]):
    access: AccessContext
    resource_id: UUID
