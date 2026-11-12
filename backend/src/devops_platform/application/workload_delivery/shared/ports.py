"""Application generation and delivery workflows, expressed as repository/provider ports."""

import re
from typing import Protocol
from uuid import UUID

from devops_platform.application.workload_delivery.attach_database.command import (
    ResourceAttachmentSpec,
)
from devops_platform.application.workload_delivery.shared.models import (
    DeliveryClaim as DeliveryClaim,
)
from devops_platform.application.workload_delivery.shared.models import (
    DeliveryResult as DeliveryResult,
)
from devops_platform.application.workload_delivery.shared.models import (
    DeliveryStepDetails as DeliveryStepDetails,
)
from devops_platform.application.workload_delivery.shared.models import (
    DeploymentDetails as DeploymentDetails,
)
from devops_platform.application.workload_delivery.shared.models import (
    GeneratedFile as GeneratedFile,
)
from devops_platform.application.workload_delivery.shared.models import (
    TemplateVersion as TemplateVersion,
)
from devops_platform.application.workload_delivery.shared.models import (
    WebhookResult as WebhookResult,
)
from devops_platform.application.workload_delivery.shared.models import (
    WorkloadDetails as WorkloadDetails,
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
        command: ResourceAttachmentSpec,
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


class WorkloadDeliveryFailure(Exception):
    def __init__(self, code: str, retryable: bool = True) -> None:
        super().__init__(code)
        self.code = code if re.fullmatch(r"[a-z][a-z0-9_]{0,79}", code) else "delivery_failed"
        self.retryable = retryable


class ApprovedImageCatalog(Protocol):
    def is_approved(self, digest: str, target_id: str) -> bool: ...


ApplicationDeliveryFailure = WorkloadDeliveryFailure
