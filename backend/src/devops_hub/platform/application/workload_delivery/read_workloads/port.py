"""Read-only projection access for application delivery."""

from typing import Protocol
from uuid import UUID

from devops_hub.platform.application.workload_delivery.shared.models import (
    DeliveryStepDetails,
    DeploymentDetails,
    WorkloadDetails,
)


class ApplicationReadRepository(Protocol):
    async def list_applications(self, project_id: UUID) -> tuple[WorkloadDetails, ...]: ...
    async def find_application(
        self, project_id: UUID, application_id: UUID
    ) -> WorkloadDetails | None: ...
    async def list_steps(self, application_id: UUID) -> tuple[DeliveryStepDetails, ...]: ...
    async def deployment_history(
        self, project_id: UUID, application_id: UUID
    ) -> tuple[DeploymentDetails, ...]: ...
