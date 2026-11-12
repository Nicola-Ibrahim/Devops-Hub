"""Temporary developer resource entity."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from devops_platform.domain.value_objects.lease import ResourceLease
from devops_platform.domain.value_objects.resource_name import ResourceName
from devops_platform.domain.value_objects.resource_spec import ResourceSpec
from devops_platform.domain.value_objects.statuses import DesiredState, ResourceStatus


@dataclass(frozen=True, slots=True)
class TemporaryResource:
    id: UUID
    project_id: UUID
    environment_id: UUID | None
    owner_id: UUID
    installation_id: UUID
    name: ResourceName
    specification: ResourceSpec
    lease: ResourceLease
    desired_state: DesiredState
    status: ResourceStatus
    revision: int
    generation: int
    created_at: datetime
    failure_code: str | None = None
