from dataclasses import dataclass
from uuid import UUID

from developer_platform.application.workload_delivery.shared.models import DeliveryStepDetails
from developer_platform.domain.access import AccessContext
from shared.dispatch import Command


@dataclass(frozen=True)
class ResourceAttachmentSpec:
    template_id: str
    version: str
    target_id: str
    size_id: str
    ttl_seconds: int


@dataclass(frozen=True, slots=True)
class AttachDatabase(Command[DeliveryStepDetails]):
    access: AccessContext
    application_id: UUID
    request: ResourceAttachmentSpec
    idempotency_key: str
