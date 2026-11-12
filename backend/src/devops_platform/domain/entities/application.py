"""Application delivery entities."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from devops_platform.domain.value_objects.image_digest import ImageDigest

ApplicationStatus = Literal["pending", "ready", "failed", "deleting", "deleted"]
DeliveryStepKind = Literal[
    "repository", "resource", "deployment", "template_update", "preview_cleanup"
]
DeliveryStepStatus = Literal["pending", "running", "succeeded", "failed"]


@dataclass(frozen=True, slots=True)
class Application:
    id: UUID
    project_id: UUID
    environment_id: UUID
    owner_id: UUID
    name: str
    template_id: str
    template_version: str
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime
    resource_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class DeliveryStep:
    id: UUID
    application_id: UUID
    kind: DeliveryStepKind
    status: DeliveryStepStatus
    attempts: int
    created_at: datetime
    updated_at: datetime
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class Deployment:
    id: UUID
    application_id: UUID
    image: ImageDigest
    target_id: str
    status: DeliveryStepStatus
    created_at: datetime
    url: str | None = None
