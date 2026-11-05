"""Retry a failed application delivery step."""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from developer_platform.application.delivery_policy import require_delivery_scope
from developer_platform.application.dto import AccessContext
from developer_platform.domain.application_delivery import (
    ApplicationDeliveryRepository,
    DeliveryStepDetails,
)


class RetryDeliveryStep:
    def __init__(
        self, repository: ApplicationDeliveryRepository, clock: Callable[[], datetime]
    ) -> None:
        self.repository, self.clock = repository, clock

    async def execute(
        self, access: AccessContext, application_id: UUID, step_id: UUID
    ) -> DeliveryStepDetails:
        require_delivery_scope(access, "resources:write")
        return await self.repository.retry_step(access, application_id, step_id, self.clock())
