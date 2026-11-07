from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class EnvironmentDetails:
    id: UUID
    name: str


@dataclass(frozen=True)
class ProjectRegistrationDetails:
    project_id: UUID
    name: str
    owning_team_id: UUID | None
    owning_team_name: str | None
    repository: str | None
    configured: bool
    environments: tuple[EnvironmentDetails, ...]
