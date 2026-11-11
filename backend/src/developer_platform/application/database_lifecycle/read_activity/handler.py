from developer_platform.application.database_lifecycle.read_activity.query import (
    ReadResourceActivity,
)
from developer_platform.domain.resource_lifecycle_repository import (
    ResourceActivity,
    ResourceLifecycleRepository,
)


class ListResourceActivityQueryHandler:
    def __init__(self, repository: ResourceLifecycleRepository) -> None:
        self.repository = repository

    async def execute(self, query: ReadResourceActivity) -> tuple[ResourceActivity, ...]:
        return await self.repository.activity(query.project_id, 100)
