"""Private resource binding requested by an application deployment."""

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class ApplicationDatabaseBinding:
    installation_id: UUID
    project_id: UUID
    application_id: UUID
    resource_id: UUID
    container_name: str
    dsn: str = field(repr=False)


class ApplicationDatabaseBindingResolver(Protocol):
    async def resolve(
        self, project_id: UUID, application_id: UUID, resource_id: UUID
    ) -> ApplicationDatabaseBinding: ...
