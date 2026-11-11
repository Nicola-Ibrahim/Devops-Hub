"""Typed public dispatch contract for developer-platform operations.

These messages are transport independent. HTTP routes translate validated
schemas and authenticated principals to these values; handlers never receive
FastAPI, Pydantic or Dishka types.
"""

from dataclasses import dataclass, field
from typing import Protocol, TypeVar
from uuid import UUID

from developer_platform.application.database_lifecycle.read_connection.query import (
    DatabaseConnection,
)
from developer_platform.application.database_lifecycle.renew_lease.command import (
    RenewDatabaseLease,
)
from developer_platform.application.database_provisioning.read_resources.query import (
    OperationDetails,
    ResourceDetails,
)
from developer_platform.application.database_provisioning.submit_database_request.command import (
    RequestDatabaseCommand,
)
from developer_platform.application.database_provisioning.submit_database_request.result import (
    AcceptedDatabaseRequest,
)
from developer_platform.application.projects.result import ProjectRegistrationDetails
from developer_platform.application.shared.dto import AccessContext, CatalogResult
from developer_platform.application.workload_delivery.attach_database.command import (
    ResourceAttachmentCommand,
)
from developer_platform.application.workload_delivery.create_workload.command import (
    ApplicationCommand,
)
from developer_platform.application.workload_delivery.deploy_workload.command import (
    DeploymentCommand,
)
from developer_platform.application.workload_delivery.shared.models import (
    ApplicationDetails,
    DeliveryStepDetails,
    DeploymentDetails,
    TemplateVersion,
    WebhookResult,
)
from developer_platform.domain.resource_lifecycle_repository import (
    ResourceActivity,
    ResourceSnapshot,
)
from shared.dispatch import Command, Query

ResultT = TypeVar("ResultT")


class DeveloperPlatformModule(Protocol):
    async def execute(self, command: Command[ResultT]) -> ResultT: ...

    async def query(self, query: Query[ResultT]) -> ResultT: ...


@dataclass(frozen=True, slots=True)
class ReadCatalog(Query[CatalogResult]):
    access: AccessContext


@dataclass(frozen=True, slots=True)
class ReadProject(Query[ProjectRegistrationDetails]):
    access: AccessContext
    project_id: UUID


@dataclass(frozen=True, slots=True)
class ReadProjects(Query[tuple[ProjectRegistrationDetails, ...]]):
    accesses: tuple[AccessContext, ...]


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
class ReadDatabaseConnection(Query[DatabaseConnection]):
    access: AccessContext
    resource_id: UUID


@dataclass(frozen=True, slots=True)
class ReadResourceActivity(Query[tuple[ResourceActivity, ...]]):
    access: AccessContext
    project_id: UUID


@dataclass(frozen=True, slots=True)
class ReadTemplates(Query[tuple[TemplateVersion, ...]]):
    pass


@dataclass(frozen=True, slots=True)
class ReadApplications(Query[tuple[ApplicationDetails, ...]]):
    access: AccessContext


@dataclass(frozen=True, slots=True)
class ReadApplication(Query[tuple[ApplicationDetails, tuple[DeliveryStepDetails, ...]]]):
    access: AccessContext
    application_id: UUID


@dataclass(frozen=True, slots=True)
class ReadDeploymentHistory(Query[tuple[DeploymentDetails, ...]]):
    access: AccessContext
    application_id: UUID


@dataclass(frozen=True, slots=True)
class RequestTemporaryDatabase(Command[AcceptedDatabaseRequest]):
    access: AccessContext
    request: RequestDatabaseCommand
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class RenewDatabase(Command[ResourceSnapshot]):
    access: AccessContext
    renewal: RenewDatabaseLease


@dataclass(frozen=True, slots=True)
class DeleteDatabase(Command[UUID]):
    access: AccessContext
    resource_id: UUID


@dataclass(frozen=True, slots=True)
class CreateApplication(Command[tuple[ApplicationDetails, bool]]):
    access: AccessContext
    request: ApplicationCommand
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class AttachDatabase(Command[DeliveryStepDetails]):
    access: AccessContext
    application_id: UUID
    request: ResourceAttachmentCommand
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class DeployApplication(Command[DeploymentDetails]):
    access: AccessContext
    application_id: UUID
    request: DeploymentCommand
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class RetryDeliveryStep(Command[DeliveryStepDetails]):
    access: AccessContext
    application_id: UUID
    step_id: UUID


@dataclass(frozen=True, slots=True)
class ProcessGithubPreviewWebhook(Command[WebhookResult]):
    raw_body: bytes = field(repr=False)
    signature: str | None = field(repr=False)
    delivery_id: str | None
    event: str | None
