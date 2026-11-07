"""Persistence required to register an application-generation request."""

from datetime import datetime
from typing import Protocol

from developer_platform.application.application_delivery.create_application.command import (
    ApplicationCommand,
)
from developer_platform.application.application_delivery.shared.models import ApplicationDetails
from developer_platform.application.shared.dto import AccessContext


class ApplicationCreationRepository(Protocol):
    async def create_application(
        self,
        access: AccessContext,
        command: ApplicationCommand,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
    ) -> tuple[ApplicationDetails, bool]: ...
