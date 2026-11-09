"""Read project applications and deployment history."""

from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.errors import PlatformRequestError
from developer_platform.application.workload_delivery.read_workloads.port import (
    ApplicationReadRepository,
)
from developer_platform.application.workload_delivery.read_workloads.query import (
    DeploymentHistoryQuery,
    GetWorkloadQuery,
    ListWorkloadsQuery,
)
from developer_platform.application.workload_delivery.shared.models import (
    DeliveryStepDetails,
    DeploymentDetails,
    WorkloadDetails,
)
from developer_platform.application.workload_delivery.shared.policy import require_delivery_scope


class ReadApplicationsQueryHandler:
    def __init__(self, repository: ApplicationReadRepository) -> None:
        self.repository = repository

    async def execute_list(
        self, access: AccessContext, query: ListWorkloadsQuery
    ) -> tuple[WorkloadDetails, ...]:
        require_delivery_scope(access, "resources:read")
        return await self.repository.list_applications(access.project_id)

    async def execute_application(
        self, access: AccessContext, query: GetWorkloadQuery
    ) -> tuple[WorkloadDetails, tuple[DeliveryStepDetails, ...]]:
        require_delivery_scope(access, "resources:read")
        workload = await self.repository.find_application(access.project_id, query.workload_id)
        if workload is None:
            raise PlatformRequestError("workload_not_found", "Workload was not found", 404)
        return workload, await self.repository.list_steps(workload.id)

    async def execute_deployment_history(
        self, access: AccessContext, query: DeploymentHistoryQuery
    ) -> tuple[DeploymentDetails, ...]:
        require_delivery_scope(access, "resources:read")
        if await self.repository.find_application(access.project_id, query.workload_id) is None:
            raise PlatformRequestError("workload_not_found", "Workload was not found", 404)
        return await self.repository.deployment_history(access.project_id, query.workload_id)


ReadWorkloadsQueryHandler = ReadApplicationsQueryHandler
