"""Database resource and lifecycle HTTP models."""

from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, Field

from api.core.schemas import Contract
from devops_hub.platform.domain import DesiredState, ResourceStatus

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]


class ResourceRequest(Contract):
    project_id: UUID
    environment_id: UUID
    version: Annotated[str, Field(pattern=r"^[0-9]{1,2}$")]
    display_name: Annotated[str, Field(min_length=1, max_length=100)]
    template_id: Identifier
    target_id: Identifier
    size_id: Identifier
    ttl_seconds: Annotated[int, Field(strict=True, ge=1, le=86400)] = 3600


class RenewRequest(Contract):
    expected_revision: Annotated[int, Field(strict=True, ge=1)]
    expires_at: AwareDatetime


class AcceptedOperation(Contract):
    resource_id: UUID
    operation_id: UUID


class ResourceView(Contract):
    id: UUID
    project_id: UUID
    owner_id: UUID
    environment_id: UUID | None
    display_name: str
    template_id: str
    target_id: str
    size_id: str
    desired_state: DesiredState
    status: ResourceStatus
    revision: int
    created_at: AwareDatetime
    expires_at: AwareDatetime
    failure_code: str | None = None


class ResourcePage(Contract):
    items: list[ResourceView]
    next_after: UUID | None


class ConnectionView(Contract):
    connection_string: str = Field(repr=False)
    host: str
    port: int
    database: str
    user: str
    instructions: str


class ActivityView(Contract):
    id: UUID
    actor_id: UUID | None
    resource_id: UUID
    operation_id: UUID
    action: str
    created_at: AwareDatetime


class ActivityPage(Contract):
    items: list[ActivityView]
