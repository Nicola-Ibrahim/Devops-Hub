from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from api.schemas import Contract
from developer_platform.domain import DesiredState, ResourceStatus

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]


class WorkReference(Contract):
    repository: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", max_length=200)]
    branch: Annotated[str, Field(min_length=1, max_length=255)]
    pull_request: Annotated[int, Field(strict=True, ge=1)] | None = None


class ResourceRequest(Contract):
    project_id: UUID
    display_name: Annotated[str, Field(min_length=1, max_length=100)]
    template_id: Identifier
    target_id: Identifier
    size_id: Identifier
    ttl_seconds: Annotated[int, Field(strict=True, ge=1, le=86400)] = 3600
    work_reference: WorkReference | None = None


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


class OperationView(Contract):
    id: UUID
    resource_id: UUID
    action: Literal["provision", "delete", "reconcile"]
    status: Literal["pending", "running", "succeeded", "failed", "cancelled"]
    attempts: int
    next_attempt_at: datetime
    error_code: str | None = None


class CatalogResponse(Contract):
    project_id: UUID
    templates: list[dict[str, str]]
    message: str
