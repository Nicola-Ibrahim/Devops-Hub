"""Host-side transaction joining identity references and platform registration."""

from devops_platform.application.projects.command import RegisterProjectCommand
from devops_platform.application.projects.handler import (
    RegisterProjectHandler,
    validate_registration,
)
from devops_platform.application.projects.result import ProjectRegistrationDetails
from devops_platform.application.shared.errors import ledger_unavailable
from identity.domain.interfaces.project_access_directory import ProjectAccessDirectory
from shared.infra.persistence.unit_of_work import DatabaseUnavailable, SqlAlchemyUnitOfWork


class RegisterProjectCommandHandler:
    def __init__(
        self,
        directory: ProjectAccessDirectory,
        register: RegisterProjectHandler,
        unit: SqlAlchemyUnitOfWork,
    ) -> None:
        self.directory = directory
        self.register = register
        self.unit = unit

    async def execute(self, command: RegisterProjectCommand) -> ProjectRegistrationDetails:
        validate_registration(command)

        async def register() -> ProjectRegistrationDetails:
            refs = await self.directory.register_references(command.name, command.owning_team)
            return await self.register.execute(command, refs.project_id, refs.team_id)

        try:
            return await self.unit.run(register, lambda result: result)
        except DatabaseUnavailable as error:
            raise ledger_unavailable() from error
