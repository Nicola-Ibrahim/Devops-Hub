"""Register a generated application from an approved template."""

from collections.abc import Callable
from datetime import datetime

from developer_platform.application.application_delivery.create_application.command import (
    ApplicationCommand,
)
from developer_platform.application.application_delivery.create_application.port import (
    ApplicationCreationRepository,
)
from developer_platform.application.application_delivery.shared.models import ApplicationDetails
from developer_platform.application.application_delivery.shared.policy import (
    APP_NAME,
    IDENTIFIER,
    require_delivery_scope,
    validate_delivery_key,
)
from developer_platform.application.application_delivery.shared.ports import (
    RequestFingerprint,
    TemplateCatalog,
)
from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.errors import PlatformRequestError


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

    async def execute(
        self, access: AccessContext, command: ApplicationCommand, idempotency_key: str
    ) -> tuple[ApplicationDetails, bool]:
        require_delivery_scope(access, "resources:write")
        validate_delivery_key(idempotency_key)
        if not APP_NAME.fullmatch(command.name):
            raise PlatformRequestError(
                "invalid_application_name", "Application name is invalid", 422
            )
        if not IDENTIFIER.fullmatch(command.template_id):
            raise PlatformRequestError("invalid_template", "Template identifier is invalid", 422)
        self.templates.get(command.template_id, command.template_version)
        return await self.repository.create_application(
            access, command, idempotency_key, self.fingerprint.for_value(command), self.clock()
        )
