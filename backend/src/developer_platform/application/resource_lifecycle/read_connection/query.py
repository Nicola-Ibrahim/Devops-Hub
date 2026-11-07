from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class GetDatabaseConnectionQuery:
    resource_id: UUID


@dataclass(frozen=True)
class DatabaseConnection:
    connection_string: str = field(repr=False)
    host: str
    port: int
    database: str
    user: str
    instructions: str
