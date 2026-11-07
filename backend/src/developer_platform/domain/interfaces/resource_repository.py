"""Persistence interface for locked temporary-resource aggregates."""

from typing import Protocol
from uuid import UUID

from developer_platform.domain.aggregates.resource_lifecycle import ResourceLifecycle


class ResourceRepository(Protocol):
    async def load_for_update(
        self, project_id: UUID, resource_id: UUID
    ) -> ResourceLifecycle | None: ...

    async def save(self, lifecycle: ResourceLifecycle) -> None: ...
