"""Read application projections and deployment history."""

from devops_hub.platform.application.shared.errors import PlatformRequestError
from devops_hub.platform.application.workload_delivery.read_workloads.port import (
    ApplicationReadRepository,
)
from devops_hub.platform.application.workload_delivery.read_workloads.query import (
    ReadApplication,
    ReadApplications,
    ReadDeploymentHistory,
)
from devops_hub.platform.application.workload_delivery.shared.models import (
    ApplicationDetails,
    DeliveryStepDetails,
    DeploymentDetails,
)


class ReadApplicationsHandler:
    def __init__(self, repository: ApplicationReadRepository) -> None:
        self.repository = repository

    async def execute(self, query: ReadApplications) -> tuple[ApplicationDetails, ...]:
        return await self.repository.list_applications(query.access.project_id)


class ReadApplicationHandler:
    def __init__(self, repository: ApplicationReadRepository) -> None:
        self.repository = repository

    async def execute(
        self, query: ReadApplication
    ) -> tuple[ApplicationDetails, tuple[DeliveryStepDetails, ...]]:
        application = await self.repository.find_application(
            query.access.project_id, query.application_id
        )
        if application is None:
            raise PlatformRequestError("workload_not_found", "Application was not found", 404)
        return application, await self.repository.list_steps(application.id)


class ReadDeploymentHistoryHandler:
    def __init__(self, repository: ApplicationReadRepository) -> None:
        self.repository = repository

    async def execute(self, query: ReadDeploymentHistory) -> tuple[DeploymentDetails, ...]:
        if (
            await self.repository.find_application(query.access.project_id, query.application_id)
            is None
        ):
            raise PlatformRequestError("workload_not_found", "Application was not found", 404)
        return await self.repository.deployment_history(
            query.access.project_id, query.application_id
        )
