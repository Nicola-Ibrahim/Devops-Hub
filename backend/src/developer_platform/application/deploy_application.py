"""Queue an approved immutable image for application deployment."""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from developer_platform.application.delivery import ApprovedImageCatalog, RequestFingerprint
from developer_platform.application.delivery_policy import (
    DIGEST,
    require_delivery_scope,
    validate_delivery_key,
)
from developer_platform.application.dto import AccessContext
from developer_platform.application.errors import PlatformRequestError
from developer_platform.domain.application_delivery import (
    ApplicationDeliveryRepository,
    DeploymentDetails,
)
from developer_platform.domain.application_delivery import (
    DeploymentCommand as DeploymentCommand,
)


class DeployApplication:
    def __init__(
        self,
        repository: ApplicationDeliveryRepository,
        images: ApprovedImageCatalog,
        fingerprint: RequestFingerprint,
        clock: Callable[[], datetime],
    ) -> None:
        self.repository, self.images = repository, images
        self.fingerprint, self.clock = fingerprint, clock

    async def execute(
        self,
        access: AccessContext,
        application_id: UUID,
        command: DeploymentCommand,
        idempotency_key: str,
    ) -> DeploymentDetails:
        require_delivery_scope(access, "resources:write")
        validate_delivery_key(idempotency_key)
        if not DIGEST.fullmatch(command.image_digest):
            raise PlatformRequestError(
                "immutable_image_required",
                "Deployment requires an image pinned by SHA-256 digest",
                422,
            )
        if not self.images.is_approved(command.image_digest, command.target_id):
            raise PlatformRequestError(
                "image_not_approved", "Image is not approved for this target", 403
            )
        return await self.repository.enqueue_deployment(
            access,
            application_id,
            command,
            idempotency_key,
            self.fingerprint.for_value(command),
            self.clock(),
        )
