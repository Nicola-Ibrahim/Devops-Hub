"""Read project applications and deployment history."""

from developer_platform.application.application_delivery.read_applications.port import (
    ApplicationReadRepository,
)
from developer_platform.application.application_delivery.read_applications.query import (
    DeploymentHistoryQuery,
    GetApplicationQuery,
    ListApplicationsQuery,
)
from developer_platform.application.application_delivery.shared.models import (
    ApplicationDetails,
    DeliveryStepDetails,
    DeploymentDetails,
)
from developer_platform.application.application_delivery.shared.policy import require_delivery_scope
from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.errors import PlatformRequestError


class ReadApplicationsQueryHandler:
    def __init__(self, repository: ApplicationReadRepository) -> None:
        self.repository = repository

    async def execute_list(
        self, access: AccessContext, query: ListApplicationsQuery
    ) -> tuple[ApplicationDetails, ...]:
        require_delivery_scope(access, "resources:read")
        return await self.repository.list_applications(access.project_id)

    async def execute_application(
        self, access: AccessContext, query: GetApplicationQuery
    ) -> tuple[ApplicationDetails, tuple[DeliveryStepDetails, ...]]:
        require_delivery_scope(access, "resources:read")
        application = await self.repository.find_application(
            access.project_id, query.application_id
        )
        if application is None:
            raise PlatformRequestError("application_not_found", "Application was not found", 404)
        return application, await self.repository.list_steps(application.id)

    async def execute_deployment_history(
        self, access: AccessContext, query: DeploymentHistoryQuery
    ) -> tuple[DeploymentDetails, ...]:
        require_delivery_scope(access, "resources:read")
        if await self.repository.find_application(access.project_id, query.application_id) is None:
            raise PlatformRequestError("application_not_found", "Application was not found", 404)
        return await self.repository.deployment_history(access.project_id, query.application_id)
