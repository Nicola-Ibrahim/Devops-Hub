"""Read registered projects, resources and their operations."""

from uuid import UUID

from developer_platform.application.database_provisioning.read_resources.port import (
    PlatformResourceReadRepository,
)
from developer_platform.application.database_provisioning.read_resources.query import (
    OperationDetails,
    ResourceDetails,
)
from developer_platform.application.projects.result import ProjectRegistrationDetails
from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.errors import PlatformRequestError, resource_not_found


class ReadPlatformResourcesQueryHandler:
    def __init__(self, repository: PlatformResourceReadRepository) -> None:
        self.repository = repository

    async def project(self, access: AccessContext, project_id: UUID) -> ProjectRegistrationDetails:
        project = await self.repository.find_project(project_id)
        if project is None:
            raise resource_not_found()
        return project

    async def resources(
        self, access: AccessContext, project_id: UUID, after: UUID | None, limit: int
    ) -> tuple[ResourceDetails, ...]:
        if not 1 <= limit <= 100:
            raise PlatformRequestError("invalid_page", "Page limit must be between 1 and 100", 422)
        return await self.repository.list_resources(project_id, after, limit)

    async def resource(self, access: AccessContext, resource_id: UUID) -> ResourceDetails:
        resource = await self.repository.find_resource(access.project_id, resource_id)
        if resource is None:
            raise resource_not_found()
        return resource

    async def operation(self, access: AccessContext, operation_id: UUID) -> OperationDetails:
        operation = await self.repository.find_operation(access.project_id, operation_id)
        if operation is None:
            raise resource_not_found()
        return operation
