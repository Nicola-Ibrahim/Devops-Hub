"""Request a database attachment for a registered application."""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.errors import PlatformRequestError
from developer_platform.application.workload_delivery.attach_database.command import (
    ResourceAttachmentCommand,
)
from developer_platform.application.workload_delivery.attach_database.port import (
    ApplicationResourceAttachmentRepository,
)
from developer_platform.application.workload_delivery.shared.models import DeliveryStepDetails
from developer_platform.application.workload_delivery.shared.policy import (
    require_delivery_scope,
    validate_delivery_key,
)
from developer_platform.application.workload_delivery.shared.ports import RequestFingerprint
from developer_platform.domain.errors import DomainError
from developer_platform.domain.value_objects.resource_spec import ResourceSpec


class AttachApplicationResourceHandler:
    def __init__(
        self,
        repository: ApplicationResourceAttachmentRepository,
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
            idempotency_key,
            self.fingerprint.for_value(command),
            self.clock(),
        )


AttachWorkloadDatabaseHandler = AttachApplicationResourceHandler
