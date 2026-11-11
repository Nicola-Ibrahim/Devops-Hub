"""Retry a failed application delivery step."""

from collections.abc import Callable
from datetime import datetime

from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.workload_delivery.retry_delivery_step.command import (
    RetryDeliveryStepCommand,
)
from developer_platform.application.workload_delivery.retry_delivery_step.port import (
    DeliveryRetryRepository,
)
from developer_platform.application.workload_delivery.shared.models import DeliveryStepDetails


class RetryDeliveryStepHandler:
    def __init__(self, repository: DeliveryRetryRepository, clock: Callable[[], datetime]) -> None:
        self.repository, self.clock = repository, clock

    async def execute(
        self, access: AccessContext, command: RetryDeliveryStepCommand
    ) -> DeliveryStepDetails:
        return await self.repository.retry_step(
            access, command.application_id, command.step_id, self.clock()
        )
