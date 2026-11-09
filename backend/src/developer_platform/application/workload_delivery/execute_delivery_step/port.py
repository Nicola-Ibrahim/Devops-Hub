"""Durable queue operations for delivery workers."""

from datetime import datetime
from typing import Protocol

from developer_platform.application.workload_delivery.shared.models import (
    DeliveryClaim,
    DeliveryResult,
)


class DeliveryWorkQueue(Protocol):
    async def claim_step(self, now: datetime, lease_seconds: int) -> DeliveryClaim | None: ...
    async def heartbeat_step(
        self, claim: DeliveryClaim, now: datetime, lease_seconds: int
    ) -> bool: ...
    async def complete_step(
        self, claim: DeliveryClaim, result: DeliveryResult, now: datetime
    ) -> bool: ...
    async def fail_step(
        self,
        claim: DeliveryClaim,
        error_code: str,
        now: datetime,
        retry_after_seconds: int,
        retryable: bool,
    ) -> bool: ...
    async def effect_is_current(self, claim: DeliveryClaim, now: datetime) -> bool: ...
