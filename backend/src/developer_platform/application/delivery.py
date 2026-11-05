"""Application generation and delivery workflows, expressed as repository/provider ports."""

import re
from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from uuid import UUID

from developer_platform.application.dto import AccessContext
from developer_platform.domain.application_delivery import (
    ApplicationCommand as ApplicationCommand,
)
from developer_platform.domain.application_delivery import (
    ApplicationDeliveryRepository as ApplicationDeliveryRepository,
)
from developer_platform.domain.application_delivery import (
    ApplicationDetails as ApplicationDetails,
)
from developer_platform.domain.application_delivery import (
    DeliveryClaim as DeliveryClaim,
)
from developer_platform.domain.application_delivery import (
    DeliveryResult as DeliveryResult,
)
from developer_platform.domain.application_delivery import (
    DeliveryStepDetails as DeliveryStepDetails,
)
from developer_platform.domain.application_delivery import (
    DeploymentCommand as DeploymentCommand,
)
from developer_platform.domain.application_delivery import (
    DeploymentDetails as DeploymentDetails,
)
from developer_platform.domain.application_delivery import (
    GeneratedFile as GeneratedFile,
)
from developer_platform.domain.application_delivery import (
    ResourceAttachmentCommand as ResourceAttachmentCommand,
)
from developer_platform.domain.application_delivery import (
    TemplateVersion as TemplateVersion,
)
from developer_platform.domain.application_delivery import (
    WebhookResult as WebhookResult,
)


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


class ApplicationDelivery:
    def __init__(
        self,
        repository: ApplicationDeliveryRepository,
        templates: TemplateCatalog,
        clock: Callable[[], datetime],
        images: ApprovedImageCatalog,
        fingerprint: RequestFingerprint,
        webhook_verifier: WebhookSignatureVerifier | None = None,
        allowed_repository_owner: str | None = None,
        preview_owner_id: UUID | None = None,
        preview_ttl_seconds: int = 14400,
    ) -> None:
        self.repository = repository
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
        from developer_platform.application.create_application import CreateApplication

        return await CreateApplication(
            self.repository, self.templates, self.fingerprint, self.clock
        ).execute(access, command, idempotency_key)

    async def list_applications(self, access: AccessContext) -> tuple[ApplicationDetails, ...]:
        from developer_platform.application.read_applications import ReadApplications

        return await ReadApplications(self.repository).list(access)

    async def application(
        self, access: AccessContext, application_id: UUID
    ) -> tuple[ApplicationDetails, tuple[DeliveryStepDetails, ...]]:
        from developer_platform.application.read_applications import ReadApplications

        return await ReadApplications(self.repository).application(access, application_id)

    async def attach_resource(
        self,
        access: AccessContext,
        application_id: UUID,
        command: ResourceAttachmentCommand,
        idempotency_key: str,
    ) -> DeliveryStepDetails:
        from developer_platform.application.attach_application_resource import (
            AttachApplicationResource,
        )

        return await AttachApplicationResource(
            self.repository, self.fingerprint, self.clock
        ).execute(access, application_id, command, idempotency_key)

    async def deploy(
        self,
        access: AccessContext,
        application_id: UUID,
        command: DeploymentCommand,
        idempotency_key: str,
    ) -> DeploymentDetails:
        from developer_platform.application.deploy_application import DeployApplication

        return await DeployApplication(
            self.repository, self.images, self.fingerprint, self.clock
        ).execute(access, application_id, command, idempotency_key)

    async def deployment_history(
        self, access: AccessContext, application_id: UUID
    ) -> tuple[DeploymentDetails, ...]:
        from developer_platform.application.read_applications import ReadApplications

        return await ReadApplications(self.repository).deployment_history(access, application_id)

    async def retry_step(
        self, access: AccessContext, application_id: UUID, step_id: UUID
    ) -> DeliveryStepDetails:
        from developer_platform.application.retry_delivery_step import RetryDeliveryStep

        return await RetryDeliveryStep(self.repository, self.clock).execute(
            access, application_id, step_id
        )

    async def process_github_webhook(
        self, *, raw_body: bytes, signature: str | None, delivery_id: str, event: str
    ) -> WebhookResult:
        from developer_platform.application.preview_webhooks import ProcessGithubPreviewWebhook

        return await ProcessGithubPreviewWebhook(
            self.repository,
            self.clock,
            self.images,
            self.webhook_verifier,
            self.allowed_repository_owner,
            self.preview_owner_id,
            self.preview_ttl_seconds,
        ).execute(raw_body=raw_body, signature=signature, delivery_id=delivery_id, event=event)
