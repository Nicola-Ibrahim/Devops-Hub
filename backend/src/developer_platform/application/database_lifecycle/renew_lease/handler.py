from developer_platform.application.database_lifecycle.renew_lease.command import RenewDatabaseLease
from developer_platform.application.shared.dto import AccessContext
from developer_platform.domain.resource_lifecycle_repository import (
    ResourceLifecycleRepository,
    ResourceSnapshot,
)


class RenewDatabaseLeaseHandler:
    def __init__(self, repository: ResourceLifecycleRepository) -> None:
        self.repository = repository

    async def execute(self, access: AccessContext, command: RenewDatabaseLease) -> ResourceSnapshot:
        return await self.repository.renew(
            project_id=access.project_id,
            actor_id=access.user_id,
            actor_role=access.role,
            scopes=access.scopes,
            resource_id=command.resource_id,
            revision=command.expected_revision,
            expiry=command.expires_at,
        )
