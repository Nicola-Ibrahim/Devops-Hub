"""Request a database attachment for a registered application."""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from developer_platform.application.delivery import RequestFingerprint
from developer_platform.application.delivery_policy import (
    require_delivery_scope,
    validate_delivery_key,
)
from developer_platform.application.dto import AccessContext
from developer_platform.application.errors import PlatformRequestError
from developer_platform.domain.application_delivery import (
    ApplicationDeliveryRepository,
    DeliveryStepDetails,
)
from developer_platform.domain.application_delivery import (
    ResourceAttachmentCommand as ResourceAttachmentCommand,
)


class AttachApplicationResource:
    def __init__(
        self,
        repository: ApplicationDeliveryRepository,
        fingerprint: RequestFingerprint,
        clock: Callable[[], datetime],
    ) -> None:
        self.repository, self.fingerprint, self.clock = repository, fingerprint, clock

    async def execute(
        self,
        access: AccessContext,
        application_id: UUID,
        command: ResourceAttachmentCommand,
        idempotency_key: str,
    ) -> DeliveryStepDetails:
        require_delivery_scope(access, "resources:write")
        validate_delivery_key(idempotency_key)
        if command.ttl_seconds < 60 or command.ttl_seconds > 86400:
            raise PlatformRequestError("invalid_lease", "Resource lifetime is outside policy", 422)
        return await self.repository.enqueue_resource_attachment(
            access,
            application_id,
            command,
            idempotency_key,
            self.fingerprint.for_value(command),
            self.clock(),
        )
