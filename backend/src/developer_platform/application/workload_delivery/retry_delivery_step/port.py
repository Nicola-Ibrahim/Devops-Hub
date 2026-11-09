"""Persistence required to retry a delivery step."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.workload_delivery.shared.models import DeliveryStepDetails


class DeliveryRetryRepository(Protocol):
    async def retry_step(
        self, access: AccessContext, workload_id: UUID, step_id: UUID, now: datetime
    ) -> DeliveryStepDetails: ...
