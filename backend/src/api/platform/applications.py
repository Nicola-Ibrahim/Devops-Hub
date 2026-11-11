"""HTTP contracts for approved application templates and delivery workflows."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends, Header, Request
from pydantic import Field

from api.dependencies import platform_access
from api.schemas import Contract
from developer_platform.application.module import (
    AttachDatabase,
    CreateApplication,
    DeployApplication,
    DeveloperPlatformModule,
    ProcessGithubPreviewWebhook,
    ReadApplication,
    ReadApplications,
    ReadDeploymentHistory,
    ReadTemplates,
    RetryDeliveryStep,
)
from developer_platform.application.shared.dto import AccessContext
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
)
from developer_platform.authorization import authorize_platform_action


class TemplateView(Contract):
    id: str
    version: str
    language: str
    name: str
    description: str


class ApplicationCreate(Contract):
    name: Annotated[str, Field(min_length=1, max_length=64)]
    environment_id: UUID
    template_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
    template_version: Annotated[str, Field(pattern=r"^[0-9]+.[0-9]+.[0-9]+$")]


class ResourceAttachment(Contract):
    template_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")] = "postgres"
    version: Annotated[str, Field(pattern=r"^[0-9]{1,2}$")] = "16"
    target_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")] = "local"
    size_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")] = "small"
    ttl_seconds: Annotated[int, Field(strict=True, ge=60, le=86400)] = 3600


class DeploymentRequest(Contract):
    image_digest: Annotated[str, Field(min_length=71, max_length=320)]
    target_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")] = "local"


class ApplicationView(Contract):
    id: UUID
    project_id: UUID
    environment_id: UUID
    owner_id: UUID
    name: str
    template_id: str
    template_version: str
    repository_url: str | None
    resource_id: UUID | None
    status: str
    created_at: datetime
    updated_at: datetime
    is_preview: bool = False
    source_repository: str | None = None
    pull_request: int | None = None
    expires_at: datetime | None = None


class DeliveryStepView(Contract):
    id: UUID
    application_id: UUID
    kind: str
    status: str
    attempts: int
    error_code: str | None
    created_at: datetime
    updated_at: datetime


class ApplicationDetail(Contract):
    application: ApplicationView
    steps: list[DeliveryStepView]


class ApplicationAccepted(Contract):
    application: ApplicationView
    replayed: bool


class DeploymentView(Contract):
    id: UUID
    application_id: UUID
    image_digest: str
    target_id: str
    status: str
    url: str | None
    created_at: datetime


class WebhookResponse(Contract):
    accepted: bool
    duplicate: bool
    application_id: UUID | None = None
    cleanup_count: int = 0
    reason: str | None = None


router = APIRouter()
PlatformAccess = Annotated[AccessContext, Depends(platform_access)]
IdempotencyKey = Annotated[str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]


def _application(row: ApplicationDetails) -> ApplicationView:
    return ApplicationView.model_validate(row.__dict__)


def _step(row: DeliveryStepDetails) -> DeliveryStepView:
    return DeliveryStepView.model_validate(row.__dict__)


def _deployment(row: DeploymentDetails) -> DeploymentView:
    return DeploymentView.model_validate(row.__dict__)


@router.get("/api/v1/templates", response_model=list[TemplateView], tags=["templates"])
@inject
async def templates(module: FromDishka[DeveloperPlatformModule]) -> list[TemplateView]:
    message = ReadTemplates()
    authorize_platform_action(message)
    return [
        TemplateView(
            id=item.template_id,
            version=item.version,
            language=item.language,
            name=item.display_name,
            description=item.description,
        )
        for item in await module.query(message)
    ]


@router.post(
    "/api/v1/applications",
    response_model=ApplicationAccepted,
    status_code=202,
    tags=["applications"],
)
@inject
async def create_application(
    body: ApplicationCreate,
    access: PlatformAccess,
    module: FromDishka[DeveloperPlatformModule],
    idempotency_key: IdempotencyKey,
) -> ApplicationAccepted:
    message = CreateApplication(access, ApplicationCommand(**body.model_dump()), idempotency_key)
    authorize_platform_action(message)
    application, replayed = await module.execute(message)
    return ApplicationAccepted(application=_application(application), replayed=replayed)


@router.get("/api/v1/applications", response_model=list[ApplicationView], tags=["applications"])
@inject
async def applications(
    access: PlatformAccess,
    module: FromDishka[DeveloperPlatformModule],
) -> list[ApplicationView]:
    message = ReadApplications(access)
    authorize_platform_action(message)
    return [_application(item) for item in await module.query(message)]


@router.get(
    "/api/v1/applications/{application_id}",
    response_model=ApplicationDetail,
    tags=["applications"],
)
@inject
async def application(
    application_id: UUID,
    access: PlatformAccess,
    module: FromDishka[DeveloperPlatformModule],
) -> ApplicationDetail:
    message = ReadApplication(access, application_id)
    authorize_platform_action(message)
    app, steps = await module.query(message)
    return ApplicationDetail(application=_application(app), steps=[_step(item) for item in steps])


@router.post(
    "/api/v1/applications/{application_id}/resources",
    response_model=DeliveryStepView,
    status_code=202,
    tags=["applications"],
)
@inject
async def attach_resource(
    application_id: UUID,
    body: ResourceAttachment,
    access: PlatformAccess,
    module: FromDishka[DeveloperPlatformModule],
    idempotency_key: IdempotencyKey,
) -> DeliveryStepView:
    message = AttachDatabase(
        access, application_id, ResourceAttachmentCommand(**body.model_dump()), idempotency_key
    )
    authorize_platform_action(message)
    step = await module.execute(message)
    return _step(step)


@router.post(
    "/api/v1/applications/{application_id}/deployments",
    response_model=DeploymentView,
    status_code=202,
    tags=["deployments"],
)
@inject
async def deploy(
    application_id: UUID,
    body: DeploymentRequest,
    access: PlatformAccess,
    module: FromDishka[DeveloperPlatformModule],
    idempotency_key: IdempotencyKey,
) -> DeploymentView:
    message = DeployApplication(
        access, application_id, DeploymentCommand(**body.model_dump()), idempotency_key
    )
    authorize_platform_action(message)
    deployment = await module.execute(message)
    return _deployment(deployment)


@router.get(
    "/api/v1/applications/{application_id}/deployments",
    response_model=list[DeploymentView],
    tags=["deployments"],
)
@inject
async def deployment_history(
    application_id: UUID,
    access: PlatformAccess,
    module: FromDishka[DeveloperPlatformModule],
) -> list[DeploymentView]:
    message = ReadDeploymentHistory(access, application_id)
    authorize_platform_action(message)
    return [_deployment(item) for item in await module.query(message)]


@router.post(
    "/api/v1/applications/{application_id}/steps/{step_id}/retry",
    response_model=DeliveryStepView,
    tags=["applications"],
)
@inject
async def retry_step(
    application_id: UUID,
    step_id: UUID,
    access: PlatformAccess,
    module: FromDishka[DeveloperPlatformModule],
) -> DeliveryStepView:
    message = RetryDeliveryStep(access, application_id, step_id)
    authorize_platform_action(message)
    return _step(await module.execute(message))


@router.post(
    "/api/v1/webhooks/github",
    response_model=WebhookResponse,
    tags=["integrations"],
)
@inject
async def github_webhook(
    request: Request,
    module: FromDishka[DeveloperPlatformModule],
) -> WebhookResponse:
    message = ProcessGithubPreviewWebhook(
        await request.body(),
        request.headers.get("x-hub-signature-256"),
        request.headers.get("x-github-delivery"),
        request.headers.get("x-github-event"),
    )
    authorize_platform_action(message)
    result = await module.execute(message)
    return WebhookResponse(
        accepted=result.accepted,
        duplicate=result.duplicate,
        application_id=result.application_id,
        cleanup_count=result.cleanup_count,
        reason=result.reason,
    )
