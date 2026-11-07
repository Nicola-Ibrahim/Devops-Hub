"""Registered project entities."""

from dataclasses import dataclass
from uuid import UUID

from developer_platform.domain.value_objects.repository_slug import RepositorySlug


@dataclass(frozen=True, slots=True)
class ProjectEnvironment:
    id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class Project:
    id: UUID
    name: str
    owning_team_id: UUID | None
    owning_team_name: str | None
    repository: RepositorySlug | None
    configured: bool
    environments: tuple[ProjectEnvironment, ...]
