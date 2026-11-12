"""Request a database attachment for a registered application."""

from collections.abc import Callable
from datetime import datetime

from devops_hub.platform.application.shared.errors import PlatformRequestError
from devops_hub.platform.application.workload_delivery.attach_database.command import (
    AttachDatabase,
)
from devops_hub.platform.application.workload_delivery.attach_database.port import (
    ApplicationResourceAttachmentRepository,
)
from devops_hub.platform.application.workload_delivery.shared.models import DeliveryStepDetails
from devops_hub.platform.application.workload_delivery.shared.policy import (
    validate_delivery_key,
)
from devops_hub.platform.application.workload_delivery.shared.ports import RequestFingerprint
from devops_hub.platform.domain.errors import DomainError
from devops_hub.platform.domain.value_objects.resource_spec import ResourceSpec


class AttachApplicationResourceHandler:
    def __init__(
        self,
        repository: ApplicationResourceAttachmentRepository,
        fingerprint: RequestFingerprint,
        clock: Callable[[], datetime],
    ) -> None:
        self.repository, self.fingerprint, self.clock = repository, fingerprint, clock

    async def execute(self, message: AttachDatabase) -> DeliveryStepDetails:
        access, application_id, command = message.access, message.application_id, message.request
        validate_delivery_key(message.idempotency_key)
        try:
            ResourceSpec(
                command.template_id,
                command.version,
                command.target_id,
                command.size_id,
                max_lifetime_seconds=86400,
            )
        except DomainError as error:
            raise PlatformRequestError(
                "invalid_resource", "Resource request is invalid", 422
            ) from error
        if command.ttl_seconds < 60 or command.ttl_seconds > 86400:
            raise PlatformRequestError("invalid_lease", "Resource lifetime is outside policy", 422)
        return await self.repository.enqueue_resource_attachment(
            access,
            application_id,
            command,
            message.idempotency_key,
            self.fingerprint.for_value(command),
            self.clock(),
        )
