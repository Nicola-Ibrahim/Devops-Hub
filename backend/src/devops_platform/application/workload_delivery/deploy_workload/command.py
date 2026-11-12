from dataclasses import dataclass
from uuid import UUID

from devops_platform.application.workload_delivery.shared.models import DeploymentDetails
from devops_platform.domain.access import AccessContext
from shared.dispatch import Command


@dataclass(frozen=True)
class DeploymentSpec:
    image_digest: str
    target_id: str = "local"


@dataclass(frozen=True, slots=True)
class DeployApplication(Command[DeploymentDetails]):
    access: AccessContext
    application_id: UUID
    request: DeploymentSpec
    idempotency_key: str
