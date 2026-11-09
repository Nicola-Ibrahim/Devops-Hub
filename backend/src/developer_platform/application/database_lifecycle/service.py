"""Compatibility-facing application service that dispatches lifecycle use cases."""

from uuid import UUID

from developer_platform.application.database_lifecycle.delete_database.command import (
    DeleteTemporaryDatabaseCommand,
)
from developer_platform.application.database_lifecycle.delete_database.handler import (
    DeleteTemporaryDatabaseHandler,
)
from developer_platform.application.database_lifecycle.ports import ResourceCredentialCipher
from developer_platform.application.database_lifecycle.read_activity.handler import (
    ListResourceActivityQueryHandler,
)
from developer_platform.application.database_lifecycle.read_activity.query import (
    ListResourceActivityQuery,
)
from developer_platform.application.database_lifecycle.read_connection.handler import (
    GetDatabaseConnectionQueryHandler,
)
from developer_platform.application.database_lifecycle.read_connection.query import (
    DatabaseConnection,
    GetDatabaseConnectionQuery,
)
from developer_platform.application.database_lifecycle.renew_lease.command import RenewDatabaseLease
from developer_platform.application.database_lifecycle.renew_lease.handler import (
    RenewDatabaseLeaseHandler,
)
from developer_platform.application.shared.dto import AccessContext
from developer_platform.domain.resource_lifecycle_repository import (
    ResourceActivity,
    ResourceLifecycleRepository,
    ResourceSnapshot,
)


class ManageDatabaseLifecycleHandler:
    """Route HTTP-host calls to one-purpose lifecycle command/query handlers."""

    def __init__(
        self, repository: ResourceLifecycleRepository, cipher: ResourceCredentialCipher | None
    ) -> None:
        self.repository, self.cipher = repository, cipher

    async def renew(self, access: AccessContext, command: RenewDatabaseLease) -> ResourceSnapshot:
        return await RenewDatabaseLeaseHandler(self.repository).execute(access, command)

    async def delete(self, access: AccessContext, resource_id: UUID) -> UUID:
        return await DeleteTemporaryDatabaseHandler(self.repository).execute(
            access, DeleteTemporaryDatabaseCommand(resource_id)
        )

    async def connection(self, access: AccessContext, resource_id: UUID) -> DatabaseConnection:
        return await GetDatabaseConnectionQueryHandler(self.repository, self.cipher).execute(
            access, GetDatabaseConnectionQuery(resource_id)
        )

    async def activity(
        self, access: AccessContext, project_id: UUID
    ) -> tuple[ResourceActivity, ...]:
        return await ListResourceActivityQueryHandler(self.repository).execute(
            access, ListResourceActivityQuery(project_id)
        )
