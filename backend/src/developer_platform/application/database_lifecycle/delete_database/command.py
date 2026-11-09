from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DeleteTemporaryDatabaseCommand:
    resource_id: UUID
