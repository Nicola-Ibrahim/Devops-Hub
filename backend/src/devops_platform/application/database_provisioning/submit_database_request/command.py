from dataclasses import dataclass
from uuid import UUID

from devops_platform.application.database_provisioning.submit_database_request.result import (
    AcceptedDatabaseRequest,
)
from devops_platform.domain.access import AccessContext
from shared.dispatch import Command


@dataclass(frozen=True)
class DatabaseRequest:
    project_id: UUID
    environment_id: UUID
    display_name: str
    template_id: str
    version: str
    target_id: str
    size_id: str
    ttl_seconds: int


@dataclass(frozen=True, slots=True)
class RequestTemporaryDatabase(Command[AcceptedDatabaseRequest]):
    access: AccessContext
    request: DatabaseRequest
    idempotency_key: str
