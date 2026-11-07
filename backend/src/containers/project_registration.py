"""Host-side transaction joining identity references and platform registration."""

from developer_platform.application.project_registration.command import RegisterProjectCommand
from developer_platform.application.project_registration.handler import (
    RegisterProjectHandler,
    validate_registration,
)
from developer_platform.application.project_registration.result import ProjectRegistrationDetails
from developer_platform.application.shared.errors import ledger_unavailable
from identity.domain.project_access import ProjectAccessDirectory
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
