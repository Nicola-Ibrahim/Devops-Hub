from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ListProjectMembersQuery:
    actor_id: UUID
    project_id: UUID
