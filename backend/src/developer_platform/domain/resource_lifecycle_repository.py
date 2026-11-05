"""Business-facing persistence contract for temporary database lifecycles."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID


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


class ResourceLifecycleRepository(Protocol):
    async def renew(
        self,
        *,
        project_id: UUID,
        actor_id: UUID,
        actor_role: Literal["developer", "admin"],
        scopes: frozenset[str],
        resource_id: UUID,
        revision: int,
        expiry: datetime,
    ) -> ResourceSnapshot: ...

    async def delete(
        self,
        *,
        project_id: UUID,
        actor_id: UUID,
        actor_role: Literal["developer", "admin"],
        scopes: frozenset[str],
        resource_id: UUID,
    ) -> UUID: ...

    async def connection(
        self,
        *,
        project_id: UUID,
        actor_id: UUID,
        actor_role: Literal["developer", "admin"],
        scopes: frozenset[str],
        resource_id: UUID,
    ) -> ResourceConnectionSecret: ...

    async def activity(self, project_id: UUID, limit: int) -> tuple[ResourceActivity, ...]: ...
