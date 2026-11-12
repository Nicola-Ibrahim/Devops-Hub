from dataclasses import dataclass
from uuid import UUID

from devops_platform.application.workload_delivery.shared.models import DeliveryStepDetails
from devops_platform.domain.access import AccessContext
from shared.dispatch import Command


@dataclass(frozen=True, slots=True)
class RetryDeliveryStep(Command[DeliveryStepDetails]):
    access: AccessContext
    application_id: UUID
    step_id: UUID
