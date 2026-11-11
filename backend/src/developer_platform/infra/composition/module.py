"""Explicit platform message bindings; use-case adapters stay in this context."""

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from developer_platform.application.database_lifecycle.delete_database.command import DeleteDatabase
from developer_platform.application.database_lifecycle.delete_database.handler import (
    DeleteTemporaryDatabaseHandler,
)
from developer_platform.application.database_lifecycle.read_activity.handler import (
    ListResourceActivityQueryHandler,
)
from developer_platform.application.database_lifecycle.read_activity.query import (
    ReadResourceActivity,
)
from developer_platform.application.database_lifecycle.read_connection.handler import (
    GetDatabaseConnectionQueryHandler,
)
from developer_platform.application.database_lifecycle.read_connection.query import (
    ReadDatabaseConnection,
)
from developer_platform.application.database_lifecycle.renew_lease.command import RenewDatabase
from developer_platform.application.database_lifecycle.renew_lease.handler import (
    RenewDatabaseLeaseHandler,
)
from developer_platform.application.database_provisioning.read_resources.handler import (
    ReadOperationHandler,
    ReadProjectHandler,
    ReadProjectsHandler,
    ReadResourceHandler,
    ReadResourcesHandler,
)
from developer_platform.application.database_provisioning.read_resources.query import (
    ReadOperation,
    ReadProject,
    ReadProjects,
    ReadResource,
    ReadResources,
)
from developer_platform.application.database_provisioning.submit_database_request.command import (
    RequestTemporaryDatabase,
)
from developer_platform.application.database_provisioning.submit_database_request.handler import (
    RequestTemporaryDatabaseHandler,
)
from developer_platform.application.resource_catalog.handler import ReadCatalogQueryHandler
from developer_platform.application.resource_catalog.query import ReadCatalog
from developer_platform.application.workload_delivery.attach_database.command import AttachDatabase
from developer_platform.application.workload_delivery.attach_database.handler import (
    AttachApplicationResourceHandler,
)
from developer_platform.application.workload_delivery.create_workload.command import (
    CreateApplication,
)
from developer_platform.application.workload_delivery.create_workload.handler import (
    CreateApplicationHandler,
)
from developer_platform.application.workload_delivery.deploy_workload.command import (
    DeployApplication,
)
from developer_platform.application.workload_delivery.deploy_workload.handler import (
    DeployApplicationHandler,
)
from developer_platform.application.workload_delivery.handle_preview_webhook.command import (
    ProcessGithubPreviewWebhook,
)
from developer_platform.application.workload_delivery.handle_preview_webhook.handler import (
    ProcessGithubPreviewWebhookHandler,
)
from developer_platform.application.workload_delivery.read_templates.handler import (
    ReadTemplatesHandler,
)
from developer_platform.application.workload_delivery.read_templates.query import ReadTemplates
from developer_platform.application.workload_delivery.read_workloads.handler import (
    ReadApplicationHandler,
    ReadApplicationsHandler,
    ReadDeploymentHistoryHandler,
)
from developer_platform.application.workload_delivery.read_workloads.query import (
    ReadApplication,
    ReadApplications,
    ReadDeploymentHistory,
)
from developer_platform.application.workload_delivery.retry_delivery_step.command import (
    RetryDeliveryStep,
)
from developer_platform.application.workload_delivery.retry_delivery_step.handler import (
    RetryDeliveryStepHandler,
)
from developer_platform.authorization import authorize_platform_action
from shared.dispatch import Command, HandlerRegistry, ModuleDispatcher, Query

ResultT = TypeVar("ResultT")


PLATFORM_HANDLER_REGISTRY = HandlerRegistry(
    commands=(
        (RequestTemporaryDatabase, RequestTemporaryDatabaseHandler),
        (RenewDatabase, RenewDatabaseLeaseHandler),
        (DeleteDatabase, DeleteTemporaryDatabaseHandler),
        (CreateApplication, CreateApplicationHandler),
        (AttachDatabase, AttachApplicationResourceHandler),
        (DeployApplication, DeployApplicationHandler),
        (RetryDeliveryStep, RetryDeliveryStepHandler),
        (ProcessGithubPreviewWebhook, ProcessGithubPreviewWebhookHandler),
    ),
    queries=(
        (ReadCatalog, ReadCatalogQueryHandler),
        (ReadProject, ReadProjectHandler),
        (ReadProjects, ReadProjectsHandler),
        (ReadResources, ReadResourcesHandler),
        (ReadResource, ReadResourceHandler),
        (ReadOperation, ReadOperationHandler),
        (ReadDatabaseConnection, GetDatabaseConnectionQueryHandler),
        (ReadResourceActivity, ListResourceActivityQueryHandler),
        (ReadTemplates, ReadTemplatesHandler),
        (ReadApplications, ReadApplicationsHandler),
        (ReadApplication, ReadApplicationHandler),
        (ReadDeploymentHistory, ReadDeploymentHistoryHandler),
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
