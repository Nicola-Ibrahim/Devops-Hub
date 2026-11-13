"""Template and application-delivery HTTP request/response models."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from api.core.schemas import Contract


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


class LocalPreviewCreate(Contract):
    name: Annotated[str, Field(min_length=1, max_length=64)]
    environment_id: UUID
    ttl_seconds: Annotated[int, Field(strict=True, ge=60, le=86400)]


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
