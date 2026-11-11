from uuid import UUID

from developer_platform.application.database_lifecycle.delete_database.command import (
    DeleteDatabase,
)
from developer_platform.domain.resource_lifecycle_repository import ResourceLifecycleRepository


class DeleteTemporaryDatabaseHandler:
    def __init__(self, repository: ResourceLifecycleRepository) -> None:
        self.repository = repository

    async def execute(self, command: DeleteDatabase) -> UUID:
        access = command.access
        return await self.repository.delete(
            project_id=access.project_id,
            actor_id=access.user_id,
            actor_role=access.role,
            scopes=access.scopes,
            resource_id=command.resource_id,
        )
