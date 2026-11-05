"""Register an approved project and its environments."""

import re
from uuid import UUID

from developer_platform.application.errors import PlatformRequestError
from developer_platform.domain.ledger import (
    PlatformLedgerRepository,
    ProjectRegistrationDetails,
    RegisterProjectCommand,
)


def validate_registration(command: RegisterProjectCommand) -> None:
    if (
        not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", command.name)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", command.owning_team)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", command.repository)
        or len(command.repository) > 200
        or not 1 <= len(command.environments) <= 20
        or len(set(command.environments)) != len(command.environments)
        or any(not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name) for name in command.environments)
    ):
        raise PlatformRequestError("invalid_registration", "Invalid project registration", 422)


class RegisterProject:
    def __init__(self, repository: PlatformLedgerRepository) -> None:
        self.repository = repository

    async def execute(
        self, command: RegisterProjectCommand, project_id: UUID, team_id: UUID
    ) -> ProjectRegistrationDetails:
        validate_registration(command)
        return await self.repository.register_project(command, project_id, team_id)
