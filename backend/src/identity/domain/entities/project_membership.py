"""A user's role in a registered project."""

from dataclasses import dataclass
from uuid import UUID

from identity.domain.value_objects.project_role import ProjectRole


@dataclass(frozen=True, slots=True)
class ProjectMembership:
    user_id: UUID
    project_id: UUID
    role: ProjectRole
