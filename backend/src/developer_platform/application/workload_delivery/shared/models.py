"""Delivery read models, durable worker values, and persistence port."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

StepKind = Literal["repository", "resource", "deployment", "template_update", "preview_cleanup"]
StepStatus = Literal["pending", "running", "succeeded", "failed"]
WorkloadStatus = Literal["pending", "ready", "failed", "deleting", "deleted"]


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
class WorkloadDetails:
    id: UUID
    project_id: UUID
    environment_id: UUID
    owner_id: UUID
    name: str
    template_id: str
    template_version: str
    repository_url: str | None
    resource_id: UUID | None
    status: WorkloadStatus
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


ApplicationDetails = WorkloadDetails
