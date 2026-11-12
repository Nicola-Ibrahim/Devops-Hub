"""Persistence interface for application delivery aggregates."""

from typing import Protocol
from uuid import UUID

from devops_hub.platform.domain.aggregates.application_delivery import ApplicationDelivery


class ApplicationRepository(Protocol):
    async def load_for_update(
        self, project_id: UUID, application_id: UUID
    ) -> ApplicationDelivery | None: ...

    async def save(self, delivery: ApplicationDelivery) -> None: ...
