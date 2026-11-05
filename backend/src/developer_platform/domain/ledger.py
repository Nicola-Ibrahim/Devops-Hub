"""Pure request-ledger contracts. No provider side effects belong in acceptance."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from developer_platform.domain.access import AccessContext


@dataclass(frozen=True)
class EnvironmentDetails:
    id: UUID
    name: str


@dataclass(frozen=True)
class ProjectRegistrationDetails:
    project_id: UUID
    name: str
    owning_team_id: UUID | None
    owning_team_name: str | None
    repository: str | None
    configured: bool
    environments: tuple[EnvironmentDetails, ...]


@dataclass(frozen=True)
class RegisterProjectCommand:
    name: str
    owning_team: str
    repository: str
    environments: tuple[str, ...]


@dataclass(frozen=True)
class ResourceSize:
    id: str
    cpu_millis: int
    memory_bytes: int
    storage_bytes: int
    storage_enforcement: str = "reservation_only"


@dataclass(frozen=True)
class PostgresOption:
    template_id: str = "postgres"
    version: str = "16"
    target_id: str = "local"
    size: ResourceSize = ResourceSize("small", 500, 536870912, 1073741824)
    max_lifetime_seconds: int = 86400
    requestable: bool = False
    unavailable_reason: str | None = "provider_not_implemented"


@dataclass(frozen=True)
class RequestDatabaseCommand:
    project_id: UUID
    environment_id: UUID
    display_name: str
    template_id: str
    version: str
    target_id: str
    size_id: str
    ttl_seconds: int


@dataclass(frozen=True)
class AcceptedDatabaseRequest:
    resource_id: UUID
    operation_id: UUID


@dataclass(frozen=True)
class ResourceDetails:
    id: UUID
    project_id: UUID
    environment_id: UUID | None
    owner_id: UUID
    display_name: str
    template_id: str
    target_id: str
    size_id: str
    desired_state: str
    status: str
    revision: int
    created_at: datetime
    expires_at: datetime
    failure_code: str | None


@dataclass(frozen=True)
class OperationDetails:
    id: UUID
    resource_id: UUID
    action: str
    status: str
    attempts: int
    next_attempt_at: datetime
    error_code: str | None


class PlatformLedgerRepository(Protocol):
    async def register_project(
        self, command: RegisterProjectCommand, project_id: UUID, team_id: UUID
    ) -> ProjectRegistrationDetails: ...
    async def find_project(self, project_id: UUID) -> ProjectRegistrationDetails | None: ...
    async def replay_request(
        self, access: AccessContext, key: str, request_hash: str
    ) -> AcceptedDatabaseRequest | None: ...
    async def accept_database_request(
        self,
        access: AccessContext,
        command: RequestDatabaseCommand,
        option: PostgresOption,
        key: str,
        request_hash: str,
        now: datetime,
        expires_at: datetime,
        installation_id: UUID,
    ) -> AcceptedDatabaseRequest: ...
    async def list_resources(
        self, project_id: UUID, after: UUID | None, limit: int
    ) -> tuple[ResourceDetails, ...]: ...
    async def find_resource(
        self, project_id: UUID, resource_id: UUID
    ) -> ResourceDetails | None: ...
    async def find_operation(
        self, project_id: UUID, operation_id: UUID
    ) -> OperationDetails | None: ...
