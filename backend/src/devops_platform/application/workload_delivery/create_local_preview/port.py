from datetime import datetime
from typing import Protocol

from devops_platform.application.shared.dto import AccessContext
from devops_platform.application.workload_delivery.create_local_preview.command import (
    LocalPreviewRegistration,
)
from devops_platform.application.workload_delivery.shared.models import WorkloadDetails


class LocalPreviewRepository(Protocol):
    async def create_local_preview(
        self,
        access: AccessContext,
        command: LocalPreviewRegistration,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
    ) -> tuple[WorkloadDetails, bool]: ...
