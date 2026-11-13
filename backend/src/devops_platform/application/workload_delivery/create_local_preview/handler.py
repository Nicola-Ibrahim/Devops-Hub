from collections.abc import Callable
from datetime import datetime

from devops_platform.application.shared.errors import PlatformRequestError
from devops_platform.application.workload_delivery.create_local_preview.command import (
    CreateLocalPreview,
)
from devops_platform.application.workload_delivery.create_local_preview.port import (
    LocalPreviewRepository,
)
from devops_platform.application.workload_delivery.shared.models import WorkloadDetails
from devops_platform.application.workload_delivery.shared.policy import (
    APP_NAME,
    validate_delivery_key,
)
from devops_platform.application.workload_delivery.shared.ports import RequestFingerprint


class CreateLocalPreviewHandler:
    def __init__(
        self,
        repository: LocalPreviewRepository,
        fingerprint: RequestFingerprint,
        clock: Callable[[], datetime],
    ) -> None:
        self.repository = repository
        self.fingerprint, self.clock = fingerprint, clock

    async def execute(self, message: CreateLocalPreview) -> tuple[WorkloadDetails, bool]:
        request = message.request
        validate_delivery_key(message.idempotency_key)
        if not APP_NAME.fullmatch(request.name):
            raise PlatformRequestError("invalid_workload_name", "Workload name is invalid", 422)
        if not 60 <= request.ttl_seconds <= 86400:
            raise PlatformRequestError("invalid_lease", "Preview lifetime is outside policy", 422)
        return await self.repository.create_local_preview(
            message.access,
            request,
            message.idempotency_key,
            self.fingerprint.for_value(request),
            self.clock(),
        )
