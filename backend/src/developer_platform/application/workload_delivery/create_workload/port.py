"""Persistence required to register an application-generation request."""

from datetime import datetime
from typing import Protocol

from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.workload_delivery.create_workload.command import (
    CreateWorkloadCommand,
)
from developer_platform.application.workload_delivery.shared.models import WorkloadDetails


class ApplicationCreationRepository(Protocol):
    async def create_application(
        self,
        access: AccessContext,
        command: CreateWorkloadCommand,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
    ) -> tuple[WorkloadDetails, bool]: ...
