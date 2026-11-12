"""Retry a failed application delivery step."""

from collections.abc import Callable
from datetime import datetime

from devops_platform.application.workload_delivery.retry_delivery_step.command import (
    RetryDeliveryStep,
)
from devops_platform.application.workload_delivery.retry_delivery_step.port import (
    DeliveryRetryRepository,
)
from devops_platform.application.workload_delivery.shared.models import DeliveryStepDetails


class RetryDeliveryStepHandler:
    def __init__(self, repository: DeliveryRetryRepository, clock: Callable[[], datetime]) -> None:
        self.repository, self.clock = repository, clock

    async def execute(self, command: RetryDeliveryStep) -> DeliveryStepDetails:
        return await self.repository.retry_step(
            command.access, command.application_id, command.step_id, self.clock()
        )
