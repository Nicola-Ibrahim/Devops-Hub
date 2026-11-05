"""Domain records and repository contract for application delivery."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from developer_platform.domain.access import AccessContext

StepKind = Literal[
    "repository",
    "resource",
    "deployment",
    "template_update",
    "preview_cleanup",
]
StepStatus = Literal["pending", "running", "succeeded", "failed"]
ApplicationStatus = Literal["pending", "ready", "failed", "deleting", "deleted"]


@dataclass(frozen=True)
class TemplateVersion:
    template_id: str
    version: str
    language: str
    display_name: str
    description: str


@dataclass(frozen=True)
class GeneratedFile:
    path: str
    content: bytes
    sha256: str


@dataclass(frozen=True)
class ApplicationCommand:
    environment_id: UUID
    name: str
    template_id: str
    template_version: str


@dataclass(frozen=True)
class ResourceAttachmentCommand:
    template_id: str
    version: str
    target_id: str
    size_id: str
    ttl_seconds: int


@dataclass(frozen=True)
class DeploymentCommand:
    image_digest: str
    target_id: str = "local"


@dataclass(frozen=True)
class ApplicationDetails:
    id: UUID
    project_id: UUID
    environment_id: UUID
    owner_id: UUID
    name: str
    template_id: str
    template_version: str
    repository_url: str | None
    resource_id: UUID | None
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime
    is_preview: bool = False
    source_repository: str | None = None
    pull_request: int | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True)
class DeliveryStepDetails:
    id: UUID
    application_id: UUID
    kind: StepKind
    status: StepStatus
    attempts: int
    error_code: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class DeploymentDetails:
    id: UUID
    application_id: UUID
    image_digest: str
    target_id: str
    status: StepStatus
    url: str | None
    created_at: datetime


@dataclass(frozen=True)
class DeliveryClaim:
    step_id: UUID
    application_id: UUID
    project_id: UUID
    environment_id: UUID
    owner_id: UUID
    application_name: str
    template_id: str
    template_version: str
    kind: StepKind
    idempotency_key: str
    claim_token: UUID
    attempts: int
    payload: dict[str, object]


@dataclass(frozen=True)
class DeliveryResult:
    repository_url: str | None = None
    resource_id: UUID | None = None
    deployment_id: UUID | None = None
    deployment_url: str | None = None
    provider_reference: str | None = None


@dataclass(frozen=True)
class RegisteredRepository:
    project_id: UUID
    environment_id: UUID
    canonical_repository: str


@dataclass(frozen=True)
class WebhookResult:
    accepted: bool
    duplicate: bool
    application_id: UUID | None
    cleanup_count: int = 0
    reason: str | None = None


class ApplicationDeliveryRepository(Protocol):
    async def create_application(
        self,
        access: AccessContext,
        command: ApplicationCommand,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
    ) -> tuple[ApplicationDetails, bool]: ...

    async def list_applications(self, project_id: UUID) -> tuple[ApplicationDetails, ...]: ...

    async def find_application(
        self, project_id: UUID, application_id: UUID
    ) -> ApplicationDetails | None: ...

    async def list_steps(self, application_id: UUID) -> tuple[DeliveryStepDetails, ...]: ...

    async def enqueue_resource_attachment(
        self,
        access: AccessContext,
        application_id: UUID,
        command: ResourceAttachmentCommand,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
    ) -> DeliveryStepDetails: ...

    async def enqueue_deployment(
        self,
        access: AccessContext,
        application_id: UUID,
        command: DeploymentCommand,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
    ) -> DeploymentDetails: ...

    async def deployment_history(
        self, project_id: UUID, application_id: UUID
    ) -> tuple[DeploymentDetails, ...]: ...

    async def retry_step(
        self, access: AccessContext, application_id: UUID, step_id: UUID, now: datetime
    ) -> DeliveryStepDetails: ...

    async def record_webhook(
        self,
        *,
        delivery_id: str,
        payload_hash: str,
        event: str,
        repository: str,
        pull_request: int | None,
        action: str,
        now: datetime,
    ) -> bool: ...

    async def find_registered_repository(self, repository: str) -> RegisteredRepository | None: ...

    async def request_preview(
        self,
        *,
        project_id: UUID,
        owner_id: UUID,
        repository: str,
        pull_request: int,
        branch: str,
        head_sha: str,
        image_digest: str | None,
        template_id: str,
        template_version: str,
        ttl_seconds: int,
        now: datetime,
    ) -> UUID | None: ...

    async def close_preview(self, *, repository: str, pull_request: int, now: datetime) -> int: ...

    async def expire_previews(self, now: datetime, limit: int) -> int: ...

    async def claim_step(self, now: datetime, lease_seconds: int) -> DeliveryClaim | None: ...

    async def heartbeat_step(
        self, claim: DeliveryClaim, now: datetime, lease_seconds: int
    ) -> bool: ...

    async def complete_step(
        self, claim: DeliveryClaim, result: DeliveryResult, now: datetime
    ) -> bool: ...

    async def fail_step(
        self,
        claim: DeliveryClaim,
        error_code: str,
        now: datetime,
        retry_after_seconds: int,
        retryable: bool,
    ) -> bool: ...
