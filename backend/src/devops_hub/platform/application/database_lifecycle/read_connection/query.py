from dataclasses import dataclass, field
from uuid import UUID

from devops_hub.platform.domain.access import AccessContext
from shared.dispatch import Query


@dataclass(frozen=True)
class DatabaseConnection:
    connection_string: str = field(repr=False)
    host: str
    port: int
    database: str
    user: str
    instructions: str


@dataclass(frozen=True, slots=True)
class ReadDatabaseConnection(Query[DatabaseConnection]):
    access: AccessContext
    resource_id: UUID
