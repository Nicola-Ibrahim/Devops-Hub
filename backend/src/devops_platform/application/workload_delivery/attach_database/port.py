"""Persistence required to attach a resource request to an application."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from devops_platform.application.shared.dto import AccessContext
from devops_platform.application.workload_delivery.attach_database.command import (
    ResourceAttachmentSpec,
)
from devops_platform.application.workload_delivery.shared.models import DeliveryStepDetails


class ApplicationResourceAttachmentRepository(Protocol):
    async def enqueue_resource_attachment(
        self,
        access: AccessContext,
        application_id: UUID,
        command: ResourceAttachmentSpec,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
    ) -> DeliveryStepDetails: ...
