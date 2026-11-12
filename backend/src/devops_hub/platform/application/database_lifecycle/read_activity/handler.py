from devops_hub.platform.application.database_lifecycle.read_activity.query import (
    ReadResourceActivity,
)
from devops_hub.platform.application.shared.resource_repository import (
    ResourceActivity,
    ResourceRepository,
)


class ListResourceActivityQueryHandler:
    def __init__(self, repository: ResourceRepository) -> None:
        self.repository = repository

    async def execute(self, query: ReadResourceActivity) -> tuple[ResourceActivity, ...]:
        return await self.repository.activity(query.project_id, 100)
