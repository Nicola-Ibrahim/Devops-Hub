from dataclasses import dataclass
from uuid import UUID

from devops_platform.application.workload_delivery.shared.models import WorkloadDetails
from devops_platform.domain.access import AccessContext
from shared.dispatch import Command


@dataclass(frozen=True, slots=True)
class LocalPreviewRegistration:
    name: str
    environment_id: UUID
    ttl_seconds: int


@dataclass(frozen=True, slots=True)
class CreateLocalPreview(Command[tuple[WorkloadDetails, bool]]):
    access: AccessContext
    request: LocalPreviewRegistration
    idempotency_key: str
