from developer_platform.application.database_lifecycle.read_activity.query import (
    ListResourceActivityQuery,
)
from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.project_access import require_project_scope
from developer_platform.domain.resource_lifecycle_repository import (
    ResourceActivity,
    ResourceLifecycleRepository,
)


class ListResourceActivityQueryHandler:
    def __init__(self, repository: ResourceLifecycleRepository) -> None:
        self.repository = repository

    async def execute(
        self, access: AccessContext, query: ListResourceActivityQuery
    ) -> tuple[ResourceActivity, ...]:
        require_project_scope(access, query.project_id, "resources:read")
        return await self.repository.activity(query.project_id, 100)
