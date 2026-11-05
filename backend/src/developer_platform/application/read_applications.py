"""Read project applications and deployment history."""

from uuid import UUID

from developer_platform.application.delivery_policy import require_delivery_scope
from developer_platform.application.dto import AccessContext
from developer_platform.application.errors import PlatformRequestError
from developer_platform.domain.application_delivery import (
    ApplicationDeliveryRepository,
    ApplicationDetails,
    DeliveryStepDetails,
    DeploymentDetails,
)


class ReadApplications:
    def __init__(self, repository: ApplicationDeliveryRepository) -> None:
        self.repository = repository

    async def list(self, access: AccessContext) -> tuple[ApplicationDetails, ...]:
        require_delivery_scope(access, "resources:read")
        return await self.repository.list_applications(access.project_id)

    async def application(
        self, access: AccessContext, application_id: UUID
    ) -> tuple[ApplicationDetails, tuple[DeliveryStepDetails, ...]]:
        require_delivery_scope(access, "resources:read")
        application = await self.repository.find_application(access.project_id, application_id)
        if application is None:
            raise PlatformRequestError("application_not_found", "Application was not found", 404)
        return application, await self.repository.list_steps(application.id)

    async def deployment_history(
        self, access: AccessContext, application_id: UUID
    ) -> tuple[DeploymentDetails, ...]:
        require_delivery_scope(access, "resources:read")
        if await self.repository.find_application(access.project_id, application_id) is None:
            raise PlatformRequestError("application_not_found", "Application was not found", 404)
        return await self.repository.deployment_history(access.project_id, application_id)
