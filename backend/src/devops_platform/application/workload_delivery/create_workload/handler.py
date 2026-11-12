"""Register a generated application from an approved template."""

from collections.abc import Callable
from datetime import datetime

from devops_platform.application.shared.errors import PlatformRequestError
from devops_platform.application.workload_delivery.create_workload.command import (
    CreateApplication,
)
from devops_platform.application.workload_delivery.create_workload.port import (
    ApplicationCreationRepository,
)
from devops_platform.application.workload_delivery.shared.models import WorkloadDetails
from devops_platform.application.workload_delivery.shared.policy import (
    APP_NAME,
    IDENTIFIER,
    validate_delivery_key,
)
from devops_platform.application.workload_delivery.shared.ports import (
    RequestFingerprint,
    TemplateCatalog,
)


class CreateApplicationHandler:
    def __init__(
        self,
        repository: ApplicationCreationRepository,
        templates: TemplateCatalog,
        fingerprint: RequestFingerprint,
        clock: Callable[[], datetime],
    ) -> None:
        self.repository, self.templates = repository, templates
        self.fingerprint, self.clock = fingerprint, clock

    async def execute(self, message: CreateApplication) -> tuple[WorkloadDetails, bool]:
        access, request = message.access, message.request
        validate_delivery_key(message.idempotency_key)
        if not APP_NAME.fullmatch(request.name):
            raise PlatformRequestError("invalid_workload_name", "Workload name is invalid", 422)
        if not IDENTIFIER.fullmatch(request.template_id):
            raise PlatformRequestError("invalid_template", "Template identifier is invalid", 422)
        self.templates.get(request.template_id, request.template_version)
        return await self.repository.create_application(
            access,
            request,
            message.idempotency_key,
            self.fingerprint.for_value(request),
            self.clock(),
        )
