from dataclasses import dataclass, field
from uuid import UUID

from identity.domain.records import ProjectMemberDetails
from shared.dispatch import Query


@dataclass(frozen=True, slots=True)
class ListProjectMembersByActorQuery:
    actor_id: UUID
    project_id: UUID


@dataclass(frozen=True, slots=True)
class ListProjectMembersQuery(Query[tuple[ProjectMemberDetails, ...]]):
    session_token: str = field(repr=False)
    project_id: UUID
