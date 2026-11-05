"""Read registered projects, resources and their operations."""

from uuid import UUID

from developer_platform.application.dto import AccessContext
from developer_platform.application.errors import PlatformRequestError, resource_not_found
from developer_platform.application.project_access import require_project_scope
from developer_platform.domain.ledger import (
    OperationDetails,
    PlatformLedgerRepository,
    ProjectRegistrationDetails,
    ResourceDetails,
)


class ReadPlatformLedger:
    def __init__(self, repository: PlatformLedgerRepository) -> None:
        self.repository = repository

    async def project(self, access: AccessContext, project_id: UUID) -> ProjectRegistrationDetails:
        require_project_scope(access, project_id, "resources:read")
        project = await self.repository.find_project(project_id)
        if project is None:
            raise resource_not_found()
        return project

    async def resources(
        self, access: AccessContext, project_id: UUID, after: UUID | None, limit: int
    ) -> tuple[ResourceDetails, ...]:
        require_project_scope(access, project_id, "resources:read")
        if not 1 <= limit <= 100:
            raise PlatformRequestError("invalid_page", "Page limit must be between 1 and 100", 422)
        return await self.repository.list_resources(project_id, after, limit)

    async def resource(self, access: AccessContext, resource_id: UUID) -> ResourceDetails:
        require_project_scope(access, access.project_id, "resources:read")
        resource = await self.repository.find_resource(access.project_id, resource_id)
        if resource is None:
            raise resource_not_found()
        return resource

    async def operation(self, access: AccessContext, operation_id: UUID) -> OperationDetails:
        require_project_scope(access, access.project_id, "resources:read")
        operation = await self.repository.find_operation(access.project_id, operation_id)
        if operation is None:
            raise resource_not_found()
        return operation
