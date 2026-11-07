from typing import Protocol
from uuid import UUID

from developer_platform.application.project_registration.command import RegisterProjectCommand
from developer_platform.application.project_registration.result import ProjectRegistrationDetails


class ProjectRegistrationRepository(Protocol):
    async def register_project(
        self, command: RegisterProjectCommand, project_id: UUID, team_id: UUID
    ) -> ProjectRegistrationDetails: ...
