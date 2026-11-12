"""Project HTTP response models."""

from uuid import UUID

from api.core.schemas import Contract


class EnvironmentView(Contract):
    id: UUID
    name: str


class ProjectRegistrationView(Contract):
    project_id: UUID
    name: str
    owning_team_id: UUID | None
    owning_team_name: str | None
    repository: str | None
    configured: bool
    environments: list[EnvironmentView]
