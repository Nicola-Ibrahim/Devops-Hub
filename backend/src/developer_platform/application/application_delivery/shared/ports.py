"""Application generation and delivery workflows, expressed as repository/provider ports."""

import re
from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from uuid import UUID

from developer_platform.application.application_delivery.attach_resource.command import (
    ResourceAttachmentCommand,
)
from developer_platform.application.application_delivery.attach_resource.port import (
    ApplicationResourceAttachmentRepository,
)
from developer_platform.application.application_delivery.create_application.command import (
    ApplicationCommand,
)
from developer_platform.application.application_delivery.create_application.port import (
    ApplicationCreationRepository,
)
from developer_platform.application.application_delivery.deploy_application.command import (
    DeploymentCommand,
)
from developer_platform.application.application_delivery.deploy_application.port import (
    ApplicationDeploymentRepository,
)
from developer_platform.application.application_delivery.process_preview_webhook.port import (
    PreviewWebhookRepository,
)
from developer_platform.application.application_delivery.read_applications.port import (
    ApplicationReadRepository,
)
from developer_platform.application.application_delivery.retry_delivery_step.port import (
    DeliveryRetryRepository,
)
from developer_platform.application.application_delivery.shared.models import (
    ApplicationDetails as ApplicationDetails,
)
from developer_platform.application.application_delivery.shared.models import (
    DeliveryClaim as DeliveryClaim,
)
from developer_platform.application.application_delivery.shared.models import (
    DeliveryResult as DeliveryResult,
)
from developer_platform.application.application_delivery.shared.models import (
    DeliveryStepDetails as DeliveryStepDetails,
)
from developer_platform.application.application_delivery.shared.models import (
    DeploymentDetails as DeploymentDetails,
)
from developer_platform.application.application_delivery.shared.models import (
    GeneratedFile as GeneratedFile,
)
from developer_platform.application.application_delivery.shared.models import (
    TemplateVersion as TemplateVersion,
)
from developer_platform.application.application_delivery.shared.models import (
    WebhookResult as WebhookResult,
)
from developer_platform.application.shared.dto import AccessContext


class TemplateCatalog(Protocol):
    def list_templates(self) -> tuple[TemplateVersion, ...]: ...

    def get(self, template_id: str, version: str) -> TemplateVersion: ...

    def render(
        self, template_id: str, version: str, values: dict[str, str]
    ) -> tuple[GeneratedFile, ...]: ...


class WebhookSignatureVerifier(Protocol):
    """Verifies a provider signature and parses its authenticated JSON payload."""

    def verify(self, raw_body: bytes, signature: str | None) -> tuple[dict[str, object], str]: ...


class RequestFingerprint(Protocol):
    def for_value(self, value: object) -> str: ...


class RepositoryProvisioner(Protocol):
    async def create_repository(
        self,
        *,
        project_id: UUID,
        application_id: UUID,
        name: str,
        template: TemplateVersion,
        files: tuple[GeneratedFile, ...],
        idempotency_key: str,
    ) -> str: ...

    async def create_update_pull_request(
        self,
        *,
        repository_url: str,
        branch: str,
        files: tuple[GeneratedFile, ...],
        idempotency_key: str,
    ) -> str: ...


class ResourceProvisioner(Protocol):
    async def request(
        self,
        *,
        project_id: UUID,
        environment_id: UUID,
        owner_id: UUID,
        command: ResourceAttachmentCommand,
        idempotency_key: str,
    ) -> UUID: ...

    async def ready(self, project_id: UUID, resource_id: UUID) -> bool: ...

    async def delete(
        self, project_id: UUID, owner_id: UUID, resource_id: UUID, idempotency_key: str
    ) -> None: ...


class ApplicationDeployer(Protocol):
    async def deploy(
        self,
        *,
        project_id: UUID,
        application_id: UUID,
        deployment_id: UUID,
        image_digest: str,
        target_id: str,
        resource_id: UUID | None,
        idempotency_key: str,
    ) -> tuple[str, str]: ...

    async def remove(
        self, project_id: UUID, application_id: UUID, idempotency_key: str
    ) -> None: ...


class ApplicationDeliveryFailure(Exception):
    def __init__(self, code: str, retryable: bool = True) -> None:
        super().__init__(code)
        self.code = code if re.fullmatch(r"[a-z][a-z0-9_]{0,79}", code) else "delivery_failed"
        self.retryable = retryable


class ApprovedImageCatalog(Protocol):
    def is_approved(self, digest: str, target_id: str) -> bool: ...


class ApplicationDeliveryService:
    def __init__(
        self,
        creation_repository: ApplicationCreationRepository,
        read_repository: ApplicationReadRepository,
        attachment_repository: ApplicationResourceAttachmentRepository,
        deployment_repository: ApplicationDeploymentRepository,
        retry_repository: DeliveryRetryRepository,
        preview_repository: PreviewWebhookRepository,
        templates: TemplateCatalog,
        clock: Callable[[], datetime],
        images: ApprovedImageCatalog,
        fingerprint: RequestFingerprint,
        webhook_verifier: WebhookSignatureVerifier | None = None,
        allowed_repository_owner: str | None = None,
        preview_owner_id: UUID | None = None,
        preview_ttl_seconds: int = 14400,
    ) -> None:
        self.creation_repository = creation_repository
        self.read_repository = read_repository
        self.attachment_repository = attachment_repository
        self.deployment_repository = deployment_repository
        self.retry_repository = retry_repository
        self.preview_repository = preview_repository
        self.templates = templates
        self.clock = clock
        self.images = images
        self.fingerprint = fingerprint
        self.webhook_verifier = webhook_verifier
        self.allowed_repository_owner = allowed_repository_owner
        self.preview_owner_id = preview_owner_id
        self.preview_ttl_seconds = preview_ttl_seconds

    def available_templates(self) -> tuple[TemplateVersion, ...]:
        return self.templates.list_templates()

    async def create_application(
        self, access: AccessContext, command: ApplicationCommand, idempotency_key: str
    ) -> tuple[ApplicationDetails, bool]:
        from developer_platform.application.application_delivery.create_application.handler import (
            CreateApplicationHandler,
        )

        return await CreateApplicationHandler(
            self.creation_repository, self.templates, self.fingerprint, self.clock
        ).execute(access, command, idempotency_key)

    async def list_applications(self, access: AccessContext) -> tuple[ApplicationDetails, ...]:
        from developer_platform.application.application_delivery.read_applications.handler import (
            ReadApplicationsQueryHandler,
        )
        from developer_platform.application.application_delivery.read_applications.query import (
            ListApplicationsQuery,
        )

        return await ReadApplicationsQueryHandler(self.read_repository).execute_list(
            access, ListApplicationsQuery()
        )

    async def application(
        self, access: AccessContext, application_id: UUID
    ) -> tuple[ApplicationDetails, tuple[DeliveryStepDetails, ...]]:
        from developer_platform.application.application_delivery.read_applications.handler import (
            ReadApplicationsQueryHandler,
        )
        from developer_platform.application.application_delivery.read_applications.query import (
            GetApplicationQuery,
        )

        return await ReadApplicationsQueryHandler(self.read_repository).execute_application(
            access, GetApplicationQuery(application_id)
        )

    async def attach_resource(
        self,
        access: AccessContext,
        application_id: UUID,
        command: ResourceAttachmentCommand,
        idempotency_key: str,
    ) -> DeliveryStepDetails:
        from developer_platform.application.application_delivery.attach_resource.handler import (
            AttachApplicationResourceHandler,
        )

        return await AttachApplicationResourceHandler(
            self.attachment_repository, self.fingerprint, self.clock
        ).execute(access, application_id, command, idempotency_key)

    async def deploy(
        self,
        access: AccessContext,
        application_id: UUID,
        command: DeploymentCommand,
        idempotency_key: str,
    ) -> DeploymentDetails:
        from developer_platform.application.application_delivery.deploy_application.handler import (
            DeployApplicationHandler,
        )

        return await DeployApplicationHandler(
            self.deployment_repository, self.images, self.fingerprint, self.clock
        ).execute(access, application_id, command, idempotency_key)

    async def deployment_history(
        self, access: AccessContext, application_id: UUID
    ) -> tuple[DeploymentDetails, ...]:
        from developer_platform.application.application_delivery.read_applications.handler import (
            ReadApplicationsQueryHandler,
        )
        from developer_platform.application.application_delivery.read_applications.query import (
            DeploymentHistoryQuery,
        )

        return await ReadApplicationsQueryHandler(self.read_repository).execute_deployment_history(
            access, DeploymentHistoryQuery(application_id)
        )

    async def retry_step(
        self, access: AccessContext, application_id: UUID, step_id: UUID
    ) -> DeliveryStepDetails:
        from ..retry_delivery_step.command import RetryDeliveryStepCommand
        from ..retry_delivery_step.handler import RetryDeliveryStepHandler

        return await RetryDeliveryStepHandler(self.retry_repository, self.clock).execute(
            access, RetryDeliveryStepCommand(application_id, step_id)
        )

    async def process_github_webhook(
        self, *, raw_body: bytes, signature: str | None, delivery_id: str, event: str
    ) -> WebhookResult:
        from ..process_preview_webhook.command import ProcessGithubPreviewWebhookCommand
        from ..process_preview_webhook.handler import ProcessGithubPreviewWebhookHandler

        return await ProcessGithubPreviewWebhookHandler(
            self.preview_repository,
            self.clock,
            self.images,
            self.webhook_verifier,
            self.allowed_repository_owner,
            self.preview_owner_id,
            self.preview_ttl_seconds,
        ).execute(ProcessGithubPreviewWebhookCommand(raw_body, signature, delivery_id, event))
