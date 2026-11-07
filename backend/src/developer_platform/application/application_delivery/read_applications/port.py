"""Read-only projection access for application delivery."""

from typing import Protocol
from uuid import UUID

from developer_platform.application.application_delivery.shared.models import (
    ApplicationDetails,
    DeliveryStepDetails,
    DeploymentDetails,
)


class ApplicationReadRepository(Protocol):
    async def list_applications(self, project_id: UUID) -> tuple[ApplicationDetails, ...]: ...
    async def find_application(
        self, project_id: UUID, application_id: UUID
    ) -> ApplicationDetails | None: ...
    async def list_steps(self, application_id: UUID) -> tuple[DeliveryStepDetails, ...]: ...
    async def deployment_history(
        self, project_id: UUID, application_id: UUID
    ) -> tuple[DeploymentDetails, ...]: ...
