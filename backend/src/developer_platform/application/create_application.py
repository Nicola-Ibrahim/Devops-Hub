"""Register a generated application from an approved template."""

from collections.abc import Callable
from datetime import datetime

from developer_platform.application.delivery import RequestFingerprint, TemplateCatalog
from developer_platform.application.delivery_policy import (
    APP_NAME,
    IDENTIFIER,
    require_delivery_scope,
    validate_delivery_key,
)
from developer_platform.application.dto import AccessContext
from developer_platform.application.errors import PlatformRequestError
from developer_platform.domain.application_delivery import (
    ApplicationCommand as ApplicationCommand,
)
from developer_platform.domain.application_delivery import (
    ApplicationDeliveryRepository,
    ApplicationDetails,
)


class CreateApplication:
    def __init__(
        self,
        repository: ApplicationDeliveryRepository,
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
