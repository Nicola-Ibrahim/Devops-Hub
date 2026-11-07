"""Persistence required to attach a resource request to an application."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from developer_platform.application.application_delivery.attach_resource.command import (
    ResourceAttachmentCommand,
)
from developer_platform.application.application_delivery.shared.models import DeliveryStepDetails
from developer_platform.application.shared.dto import AccessContext


class ApplicationResourceAttachmentRepository(Protocol):
    async def enqueue_resource_attachment(
        self,
        access: AccessContext,
        application_id: UUID,
        command: ResourceAttachmentCommand,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
    ) -> DeliveryStepDetails: ...
