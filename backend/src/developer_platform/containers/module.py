"""Explicit platform message bindings; use-case adapters stay in this context."""

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar
from uuid import UUID

from developer_platform.application.database_lifecycle.read_connection.query import (
    DatabaseConnection,
)
from developer_platform.application.database_lifecycle.service import ManageDatabaseLifecycleHandler
from developer_platform.application.database_provisioning.read_resources.handler import (
    ReadPlatformResourcesQueryHandler,
)
from developer_platform.application.database_provisioning.read_resources.query import (
    OperationDetails,
    ResourceDetails,
)
from developer_platform.application.database_provisioning.submit_database_request.handler import (
    RequestTemporaryDatabaseHandler,
)
from developer_platform.application.database_provisioning.submit_database_request.result import (
    AcceptedDatabaseRequest,
)
from developer_platform.application.module import (
    AttachDatabase,
    CreateApplication,
    DeleteDatabase,
    DeployApplication,
    ProcessGithubPreviewWebhook,
    ReadApplication,
    ReadApplications,
    ReadCatalog,
    ReadDatabaseConnection,
    ReadDeploymentHistory,
    ReadOperation,
    ReadProject,
    ReadProjects,
    ReadResource,
    ReadResourceActivity,
    ReadResources,
    ReadTemplates,
    RenewDatabase,
    RequestTemporaryDatabase,
    RetryDeliveryStep,
)
from developer_platform.application.projects.result import ProjectRegistrationDetails
from developer_platform.application.resource_catalog.handler import ReadCatalogQueryHandler
from developer_platform.application.shared.dto import CatalogResult
from developer_platform.application.shared.errors import PlatformRequestError
from developer_platform.application.workload_delivery.shared.models import (
    ApplicationDetails,
    DeliveryStepDetails,
    DeploymentDetails,
    TemplateVersion,
    WebhookResult,
)
from developer_platform.application.workload_delivery.shared.ports import (
    ApplicationDeliveryService,
    TemplateCatalog,
)
from developer_platform.authorization import authorize_platform_action
from developer_platform.domain.resource_lifecycle_repository import (
    ResourceActivity,
    ResourceSnapshot,
)
from shared.dispatch import Command, HandlerRegistry, ModuleDispatcher, Query

ResultT = TypeVar("ResultT")


class CatalogAdapter:
    def __init__(self, handler: ReadCatalogQueryHandler) -> None:
        self.handler = handler

    async def execute(self, query: ReadCatalog) -> CatalogResult:
        return self.handler.execute(query.access)


class ProjectAdapter:
    def __init__(self, handler: ReadPlatformResourcesQueryHandler) -> None:
        self.handler = handler

    async def execute(self, query: ReadProject) -> ProjectRegistrationDetails:
        return await self.handler.project(query.access, query.project_id)


class ProjectsAdapter:
    def __init__(self, handler: ReadPlatformResourcesQueryHandler) -> None:
        self.handler = handler

    async def execute(self, query: ReadProjects) -> tuple[ProjectRegistrationDetails, ...]:
        return tuple(
            [await self.handler.project(access, access.project_id) for access in query.accesses]
        )


class ResourcesAdapter:
    def __init__(self, handler: ReadPlatformResourcesQueryHandler) -> None:
        self.handler = handler

    async def execute(self, query: ReadResources) -> tuple[ResourceDetails, ...]:
        return await self.handler.resources(
            query.access, query.project_id, query.after, query.limit
        )


class ResourceAdapter:
    def __init__(self, handler: ReadPlatformResourcesQueryHandler) -> None:
        self.handler = handler

    async def execute(self, query: ReadResource) -> ResourceDetails:
        return await self.handler.resource(query.access, query.resource_id)


class OperationAdapter:
    def __init__(self, handler: ReadPlatformResourcesQueryHandler) -> None:
        self.handler = handler

    async def execute(self, query: ReadOperation) -> OperationDetails:
        return await self.handler.operation(query.access, query.operation_id)


class RequestDatabaseAdapter:
    def __init__(self, handler: RequestTemporaryDatabaseHandler) -> None:
        self.handler = handler

    async def execute(self, command: RequestTemporaryDatabase) -> AcceptedDatabaseRequest:
        return await self.handler.execute(command.access, command.request, command.idempotency_key)


class RenewDatabaseAdapter:
    def __init__(self, handler: ManageDatabaseLifecycleHandler) -> None:
        self.handler = handler

    async def execute(self, command: RenewDatabase) -> ResourceSnapshot:
        return await self.handler.renew(command.access, command.renewal)


class DeleteDatabaseAdapter:
    def __init__(self, handler: ManageDatabaseLifecycleHandler) -> None:
        self.handler = handler

    async def execute(self, command: DeleteDatabase) -> UUID:
        return await self.handler.delete(command.access, command.resource_id)


class ConnectionAdapter:
    def __init__(self, handler: ManageDatabaseLifecycleHandler) -> None:
        self.handler = handler

    async def execute(self, query: ReadDatabaseConnection) -> DatabaseConnection:
        return await self.handler.connection(query.access, query.resource_id)


class ActivityAdapter:
    def __init__(self, handler: ManageDatabaseLifecycleHandler) -> None:
        self.handler = handler

    async def execute(self, query: ReadResourceActivity) -> tuple[ResourceActivity, ...]:
        return await self.handler.activity(query.access, query.project_id)


class TemplatesAdapter:
    def __init__(self, templates: TemplateCatalog) -> None:
        self.templates = templates

    async def execute(self, query: ReadTemplates) -> tuple[TemplateVersion, ...]:
        del query
        return self.templates.list_templates()


class ApplicationsAdapter:
    def __init__(self, service: ApplicationDeliveryService) -> None:
        self.service = service

    async def execute(self, query: ReadApplications) -> tuple[ApplicationDetails, ...]:
        return await self.service.list_workloads(query.access)


class ApplicationAdapter:
    def __init__(self, service: ApplicationDeliveryService) -> None:
        self.service = service

    async def execute(
        self, query: ReadApplication
    ) -> tuple[ApplicationDetails, tuple[DeliveryStepDetails, ...]]:
        return await self.service.workload(query.access, query.application_id)


class CreateApplicationAdapter:
    def __init__(self, service: ApplicationDeliveryService) -> None:
        self.service = service

    async def execute(self, command: CreateApplication) -> tuple[ApplicationDetails, bool]:
        return await self.service.create_workload(
            command.access, command.request, command.idempotency_key
        )


class AttachDatabaseAdapter:
    def __init__(self, service: ApplicationDeliveryService) -> None:
        self.service = service

    async def execute(self, command: AttachDatabase) -> DeliveryStepDetails:
        return await self.service.attach_database(
            command.access,
            command.application_id,
            command.request,
            command.idempotency_key,
        )


class DeployApplicationAdapter:
    def __init__(self, service: ApplicationDeliveryService) -> None:
        self.service = service

    async def execute(self, command: DeployApplication) -> DeploymentDetails:
        return await self.service.deploy(
            command.access,
            command.application_id,
            command.request,
            command.idempotency_key,
        )


class DeploymentHistoryAdapter:
    def __init__(self, service: ApplicationDeliveryService) -> None:
        self.service = service

    async def execute(self, query: ReadDeploymentHistory) -> tuple[DeploymentDetails, ...]:
        return await self.service.deployment_history(query.access, query.application_id)


class RetryDeliveryStepAdapter:
    def __init__(self, service: ApplicationDeliveryService) -> None:
        self.service = service

    async def execute(self, command: RetryDeliveryStep) -> DeliveryStepDetails:
        return await self.service.retry_step(
            command.access, command.application_id, command.step_id
        )


class WebhookAdapter:
    def __init__(self, service: ApplicationDeliveryService) -> None:
        self.service = service

    async def execute(self, command: ProcessGithubPreviewWebhook) -> WebhookResult:
        if command.delivery_id is None or command.event is None:
            raise PlatformRequestError(
                "webhook_invalid", "GitHub delivery headers are required", 400
            )
        return await self.service.process_github_webhook(
            raw_body=command.raw_body,
            signature=command.signature,
            delivery_id=command.delivery_id,
            event=command.event,
        )


PLATFORM_HANDLER_REGISTRY = HandlerRegistry(
    commands=(
        (RequestTemporaryDatabase, RequestDatabaseAdapter),
        (RenewDatabase, RenewDatabaseAdapter),
        (DeleteDatabase, DeleteDatabaseAdapter),
        (CreateApplication, CreateApplicationAdapter),
        (AttachDatabase, AttachDatabaseAdapter),
        (DeployApplication, DeployApplicationAdapter),
        (RetryDeliveryStep, RetryDeliveryStepAdapter),
        (ProcessGithubPreviewWebhook, WebhookAdapter),
    ),
    queries=(
        (ReadCatalog, CatalogAdapter),
        (ReadProject, ProjectAdapter),
        (ReadProjects, ProjectsAdapter),
        (ReadResources, ResourcesAdapter),
        (ReadResource, ResourceAdapter),
        (ReadOperation, OperationAdapter),
        (ReadDatabaseConnection, ConnectionAdapter),
        (ReadResourceActivity, ActivityAdapter),
        (ReadTemplates, TemplatesAdapter),
        (ReadApplications, ApplicationsAdapter),
        (ReadApplication, ApplicationAdapter),
        (ReadDeploymentHistory, DeploymentHistoryAdapter),
    ),
)


class _DeveloperPlatformDispatcher(ModuleDispatcher):
    """Internal handler dispatcher; only authenticated hosts expose the module contract."""

    def __init__(self, resolve_handler: Callable[[type[Any]], Awaitable[Any]]) -> None:
        super().__init__(PLATFORM_HANDLER_REGISTRY, resolve_handler)

    async def execute(self, command: Command[ResultT]) -> ResultT:
        authorize_platform_action(command)
        return await super().execute(command)

    async def query(self, query: Query[ResultT]) -> ResultT:
        authorize_platform_action(query)
        return await super().query(query)
