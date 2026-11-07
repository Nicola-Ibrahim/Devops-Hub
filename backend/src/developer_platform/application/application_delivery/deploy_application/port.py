"""Persistence required to queue an application deployment."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from developer_platform.application.application_delivery.deploy_application.command import (
    DeploymentCommand,
)
from developer_platform.application.application_delivery.shared.models import DeploymentDetails
from developer_platform.application.shared.dto import AccessContext


class ApplicationDeploymentRepository(Protocol):
    async def enqueue_deployment(
        self,
        access: AccessContext,
        application_id: UUID,
        command: DeploymentCommand,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
    ) -> DeploymentDetails: ...
