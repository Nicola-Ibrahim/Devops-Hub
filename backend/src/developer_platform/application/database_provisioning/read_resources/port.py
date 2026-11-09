from typing import Protocol
from uuid import UUID

from developer_platform.application.database_provisioning.read_resources.query import (
    OperationDetails,
    ResourceDetails,
)
from developer_platform.application.projects.result import ProjectRegistrationDetails


class PlatformResourceReadRepository(Protocol):
    async def find_project(self, project_id: UUID) -> ProjectRegistrationDetails | None: ...
    async def list_resources(
        self, project_id: UUID, after: UUID | None, limit: int
    ) -> tuple[ResourceDetails, ...]: ...
    async def find_resource(
        self, project_id: UUID, resource_id: UUID
    ) -> ResourceDetails | None: ...
    async def find_operation(
        self, project_id: UUID, operation_id: UUID
    ) -> OperationDetails | None: ...
