from developer_platform.application.database_lifecycle.renew_lease.command import RenewDatabase
from developer_platform.application.shared.resource_repository import (
    ResourceRepository,
    ResourceSnapshot,
)


class RenewDatabaseLeaseHandler:
    def __init__(self, repository: ResourceRepository) -> None:
        self.repository = repository

    async def execute(self, command: RenewDatabase) -> ResourceSnapshot:
        access = command.access
        return await self.repository.renew(
            access=access,
            resource_id=command.resource_id,
            revision=command.expected_revision,
            expiry=command.expires_at,
        )
