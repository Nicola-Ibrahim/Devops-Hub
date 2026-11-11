from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from developer_platform.application.projects.result import ProjectRegistrationDetails
from developer_platform.domain.access import AccessContext
from shared.dispatch import Query


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


@dataclass(frozen=True, slots=True)
class ReadResources(Query[tuple[ResourceDetails, ...]]):
    access: AccessContext
    project_id: UUID
    after: UUID | None
    limit: int


@dataclass(frozen=True, slots=True)
class ReadResource(Query[ResourceDetails]):
    access: AccessContext
    resource_id: UUID


@dataclass(frozen=True, slots=True)
class ReadOperation(Query[OperationDetails]):
    access: AccessContext
    operation_id: UUID


@dataclass(frozen=True, slots=True)
class ReadProject(Query[ProjectRegistrationDetails]):
    access: AccessContext
    project_id: UUID


@dataclass(frozen=True, slots=True)
class ReadProjects(Query[tuple[ProjectRegistrationDetails, ...]]):
    accesses: tuple[AccessContext, ...]
