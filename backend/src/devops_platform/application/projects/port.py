from typing import Protocol
from uuid import UUID

from devops_platform.application.projects.command import RegisterProjectCommand
from devops_platform.application.projects.result import ProjectRegistrationDetails


class ProjectRegistrationRepository(Protocol):
    async def find_project(self, project_id: UUID) -> ProjectRegistrationDetails | None: ...

    async def register_project(
        self, command: RegisterProjectCommand, project_id: UUID, team_id: UUID
    ) -> ProjectRegistrationDetails: ...
