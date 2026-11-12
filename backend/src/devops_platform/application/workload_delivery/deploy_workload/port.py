"""Persistence required to queue an application deployment."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from devops_platform.application.shared.dto import AccessContext
from devops_platform.application.workload_delivery.deploy_workload.command import (
    DeploymentSpec,
)
from devops_platform.application.workload_delivery.shared.models import DeploymentDetails


class ApplicationDeploymentRepository(Protocol):
    async def enqueue_deployment(
        self,
        access: AccessContext,
        application_id: UUID,
        command: DeploymentSpec,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
    ) -> DeploymentDetails: ...
