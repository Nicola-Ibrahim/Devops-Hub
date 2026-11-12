from uuid import UUID

from devops_platform.application.database_lifecycle.delete_database.command import (
    DeleteDatabase,
)
from devops_platform.application.shared.resource_repository import ResourceRepository


class DeleteTemporaryDatabaseHandler:
    def __init__(self, repository: ResourceRepository) -> None:
        self.repository = repository

    async def execute(self, command: DeleteDatabase) -> UUID:
        access = command.access
        return await self.repository.delete(access=access, resource_id=command.resource_id)
