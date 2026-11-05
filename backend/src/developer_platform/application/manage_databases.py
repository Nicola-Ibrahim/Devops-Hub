"""Authorized lifecycle actions for developer-requested databases."""

from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import quote
from uuid import UUID

from developer_platform.application.dto import AccessContext
from developer_platform.application.errors import PlatformRequestError
from developer_platform.application.lifecycle import ResourceCredentialCipher
from developer_platform.application.requests import require_project_scope
from developer_platform.domain.resource_lifecycle_repository import (
    ResourceActivity,
    ResourceLifecycleRepository,
    ResourceSnapshot,
)


@dataclass(frozen=True)
class RenewDatabaseLease:
    resource_id: UUID
    expected_revision: int
    expires_at: datetime


@dataclass(frozen=True)
class DatabaseConnection:
    connection_string: str = field(repr=False)
    host: str
    port: int
    database: str
    user: str
    instructions: str


class ManageDatabases:
    def __init__(
        self, repository: ResourceLifecycleRepository, cipher: ResourceCredentialCipher | None
    ) -> None:
        self.repository = repository
        self.cipher = cipher

    async def renew(self, access: AccessContext, command: RenewDatabaseLease) -> ResourceSnapshot:
        require_project_scope(access, access.project_id, "resources:write")
        return await self.repository.renew(
            project_id=access.project_id,
            actor_id=access.user_id,
            actor_role=access.role,
            scopes=access.scopes,
            resource_id=command.resource_id,
            revision=command.expected_revision,
            expiry=command.expires_at,
        )

    async def delete(self, access: AccessContext, resource_id: UUID) -> UUID:
        require_project_scope(access, access.project_id, "resources:write")
        return await self.repository.delete(
            project_id=access.project_id,
            actor_id=access.user_id,
            actor_role=access.role,
            scopes=access.scopes,
            resource_id=resource_id,
        )

    async def connection(self, access: AccessContext, resource_id: UUID) -> DatabaseConnection:
        require_project_scope(access, access.project_id, "connections:read")
        if self.cipher is None:
            raise PlatformRequestError(
                "credentials_unavailable", "Resource access is unavailable", 503
            )
        secret = await self.repository.connection(
            project_id=access.project_id,
            actor_id=access.user_id,
            actor_role=access.role,
            scopes=access.scopes,
            resource_id=resource_id,
        )
        credentials = self.cipher.decrypt(secret.resource_id, secret.ciphertext, secret.key_id)
        hostpart = f"[{secret.host}]" if ":" in secret.host else secret.host
        dsn = (
            f"postgresql://{quote(credentials.user, safe='')}:"
            f"{quote(credentials.password, safe='')}@{hostpart}:{secret.port}/"
            f"{quote(credentials.database, safe='')}"
        )
        return DatabaseConnection(
            connection_string=dsn,
            host=secret.host,
            port=secret.port,
            database=credentials.database,
            user=credentials.user,
            instructions=(
                "Connect from the configured developer host or approved tunnel. "
                "This temporary database and its stored data are removed "
                "on deletion or lease expiry."
            ),
        )

    async def activity(
        self, access: AccessContext, project_id: UUID
    ) -> tuple[ResourceActivity, ...]:
        require_project_scope(access, project_id, "resources:read")
        return await self.repository.activity(project_id, 100)
