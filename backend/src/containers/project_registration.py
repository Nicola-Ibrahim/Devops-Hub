"""Host-side transaction joining identity references and platform registration."""

from developer_platform.application.errors import ledger_unavailable
from developer_platform.application.ledger import ProjectRegistrationDetails, RegisterProjectCommand
from developer_platform.application.requests import RegisterProject, validate_registration
from identity.application.project_directory import ProjectAccessDirectory
from shared.infra.persistence.unit_of_work import DatabaseUnavailable, SqlAlchemyUnitOfWork


class RegisterProjectCommandHandler:
    def __init__(
        self,
        directory: ProjectAccessDirectory,
        register: RegisterProject,
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
