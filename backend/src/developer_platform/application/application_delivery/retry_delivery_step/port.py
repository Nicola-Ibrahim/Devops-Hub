"""Persistence required to retry a delivery step."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from developer_platform.application.application_delivery.shared.models import DeliveryStepDetails
from developer_platform.application.shared.dto import AccessContext


class DeliveryRetryRepository(Protocol):
    async def retry_step(
        self, access: AccessContext, application_id: UUID, step_id: UUID, now: datetime
    ) -> DeliveryStepDetails: ...
