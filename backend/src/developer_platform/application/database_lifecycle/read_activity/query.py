from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListResourceActivityQuery:
    project_id: UUID
