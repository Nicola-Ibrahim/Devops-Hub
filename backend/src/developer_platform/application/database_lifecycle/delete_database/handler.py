from uuid import UUID

from developer_platform.application.database_lifecycle.delete_database.command import (
    DeleteTemporaryDatabaseCommand,
)
from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.project_access import require_project_scope
from developer_platform.domain.resource_lifecycle_repository import ResourceLifecycleRepository


class DeleteTemporaryDatabaseHandler:
    def __init__(self, repository: ResourceLifecycleRepository) -> None:
        self.repository = repository

    async def execute(self, access: AccessContext, command: DeleteTemporaryDatabaseCommand) -> UUID:
        require_project_scope(access, access.project_id, "resources:write")
        return await self.repository.delete(
            project_id=access.project_id,
            actor_id=access.user_id,
            actor_role=access.role,
            scopes=access.scopes,
            resource_id=command.resource_id,
        )
