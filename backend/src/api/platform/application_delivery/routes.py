"""Application template, creation, deployment and webhook routes."""

from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends, Header, Request

from api.core.dependencies import platform_access
from api.platform.application_delivery.schemas import (
    ApplicationAccepted,
    ApplicationCreate,
    ApplicationDetail,
    ApplicationView,
    DeliveryStepView,
    DeploymentRequest,
    DeploymentView,
    ResourceAttachment,
    TemplateView,
    WebhookResponse,
)
from devops_hub.platform.application.module import DeveloperPlatformModule
from devops_hub.platform.application.shared.dto import AccessContext
from devops_hub.platform.application.workload_delivery.attach_database.command import (
    AttachDatabase,
    ResourceAttachmentSpec,
)
from devops_hub.platform.application.workload_delivery.create_workload.command import (
    ApplicationRegistration,
    CreateApplication,
)
from devops_hub.platform.application.workload_delivery.deploy_workload.command import (
    DeployApplication,
    DeploymentSpec,
)
from devops_hub.platform.application.workload_delivery.handle_preview_webhook.command import (
    ProcessGithubPreviewWebhook,
)
from devops_hub.platform.application.workload_delivery.read_templates.query import ReadTemplates
from devops_hub.platform.application.workload_delivery.read_workloads.query import (
    ReadApplication,
    ReadApplications,
    ReadDeploymentHistory,
)
from devops_hub.platform.application.workload_delivery.retry_delivery_step.command import (
    RetryDeliveryStep,
)
from devops_hub.platform.application.workload_delivery.shared.models import (
    ApplicationDetails,
    DeliveryStepDetails,
    DeploymentDetails,
)
from devops_hub.platform.authorization import authorize_platform_action

router = APIRouter()
PlatformAccess = Annotated[AccessContext, Depends(platform_access)]
IdempotencyKey = Annotated[str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]


def _application(row: ApplicationDetails) -> ApplicationView:
    return ApplicationView.model_validate(row.__dict__)


def _step(row: DeliveryStepDetails) -> DeliveryStepView:
    return DeliveryStepView.model_validate(row.__dict__)


def _deployment(row: DeploymentDetails) -> DeploymentView:
    return DeploymentView.model_validate(row.__dict__)


@router.get("/templates", response_model=list[TemplateView], tags=["templates"])
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
    "/applications",
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
    message = CreateApplication(
        access, ApplicationRegistration(**body.model_dump()), idempotency_key
    )
    authorize_platform_action(message)
    application, replayed = await module.execute(message)
    return ApplicationAccepted(application=_application(application), replayed=replayed)


@router.get("/applications", response_model=list[ApplicationView], tags=["applications"])
@inject
async def applications(
    access: PlatformAccess,
    module: FromDishka[DeveloperPlatformModule],
) -> list[ApplicationView]:
    message = ReadApplications(access)
    authorize_platform_action(message)
    return [_application(item) for item in await module.query(message)]


@router.get(
    "/applications/{application_id}",
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
    "/applications/{application_id}/resources",
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
        access, application_id, ResourceAttachmentSpec(**body.model_dump()), idempotency_key
    )
    authorize_platform_action(message)
    step = await module.execute(message)
    return _step(step)


@router.post(
    "/applications/{application_id}/deployments",
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
        access, application_id, DeploymentSpec(**body.model_dump()), idempotency_key
    )
    authorize_platform_action(message)
    deployment = await module.execute(message)
    return _deployment(deployment)


@router.get(
    "/applications/{application_id}/deployments",
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
    "/applications/{application_id}/steps/{step_id}/retry",
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
    "/webhooks/github",
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
