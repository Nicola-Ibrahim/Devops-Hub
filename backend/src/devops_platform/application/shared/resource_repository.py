"""Application contract and projections for the resource aggregate repository."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

from devops_platform.application.database_provisioning.read_resources.query import (
    OperationDetails,
    ResourceDetails,
)
from devops_platform.application.shared.dto import AccessContext
from devops_platform.domain.aggregates.resource_lifecycle import ResourceLifecycle
from devops_platform.domain.entities.operation import AcceptedResourceRequest
from devops_platform.domain.value_objects.idempotency_key import IdempotencyKey


@dataclass(frozen=True)
class ResourceSnapshot:
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
class ResourceConnectionSecret:
    resource_id: UUID
    host: str
    port: int
    ciphertext: bytes = field(repr=False)
    key_id: str


@dataclass(frozen=True)
class ResourceActivity:
    id: UUID
    actor_id: UUID | None
    resource_id: UUID
    operation_id: UUID
    action: str
    created_at: datetime


class ResourceRepository(Protocol):
    """Resource aggregate persistence used by application use cases and queries."""

    async def replay_request(
        self, access: AccessContext, key: IdempotencyKey, request_hash: str
    ) -> AcceptedResourceRequest | None: ...

    async def accept_database_request(
        self,
        access: AccessContext,
        lifecycle: ResourceLifecycle,
        key: IdempotencyKey,
        request_hash: str,
    ) -> AcceptedResourceRequest: ...

    async def renew(
        self, *, access: AccessContext, resource_id: UUID, revision: int, expiry: datetime
    ) -> ResourceSnapshot: ...

    async def delete(self, *, access: AccessContext, resource_id: UUID) -> UUID: ...

    async def connection(
        self, *, access: AccessContext, resource_id: UUID
    ) -> ResourceConnectionSecret: ...

    async def activity(self, project_id: UUID, limit: int) -> tuple[ResourceActivity, ...]: ...

    async def list_resources(
        self, project_id: UUID, after: UUID | None, limit: int
    ) -> tuple[ResourceDetails, ...]: ...

    async def find_resource(
        self, project_id: UUID, resource_id: UUID
    ) -> ResourceDetails | None: ...

    async def find_operation(
        self, project_id: UUID, operation_id: UUID
    ) -> OperationDetails | None: ...
