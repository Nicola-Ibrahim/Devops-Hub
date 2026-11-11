"""Queue an approved immutable image for application deployment."""

from collections.abc import Callable
from datetime import datetime

from developer_platform.application.shared.errors import PlatformRequestError
from developer_platform.application.workload_delivery.deploy_workload.command import (
    DeployApplication,
)
from developer_platform.application.workload_delivery.deploy_workload.port import (
    ApplicationDeploymentRepository,
)
from developer_platform.application.workload_delivery.shared.models import DeploymentDetails
from developer_platform.application.workload_delivery.shared.policy import (
    validate_delivery_key,
)
from developer_platform.application.workload_delivery.shared.ports import (
    ApprovedImageCatalog,
    RequestFingerprint,
)
from developer_platform.domain.errors import DomainError
from developer_platform.domain.value_objects.image_digest import ImageDigest


class DeployApplicationHandler:
    def __init__(
        self,
        repository: ApplicationDeploymentRepository,
        images: ApprovedImageCatalog,
        fingerprint: RequestFingerprint,
        clock: Callable[[], datetime],
    ) -> None:
        self.repository, self.images = repository, images
        self.fingerprint, self.clock = fingerprint, clock

    async def execute(self, message: DeployApplication) -> DeploymentDetails:
        access, application_id, command = message.access, message.application_id, message.request
        validate_delivery_key(message.idempotency_key)
        try:
            image = ImageDigest(command.image_digest)
        except DomainError as error:
            raise PlatformRequestError(
                "immutable_image_required",
                "Deployment requires an image pinned by SHA-256 digest",
                422,
            ) from error
        if not self.images.is_approved(image.value, command.target_id):
            raise PlatformRequestError(
                "image_not_approved", "Image is not approved for this target", 403
            )
        return await self.repository.enqueue_deployment(
            access,
            application_id,
            command,
            message.idempotency_key,
            self.fingerprint.for_value(command),
            self.clock(),
        )
