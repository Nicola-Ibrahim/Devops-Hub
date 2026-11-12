from collections.abc import Callable
from datetime import datetime

from identity.application.bootstrap_first_admin.command import BootstrapFirstAdminCommand
from identity.domain.interfaces.user_repository import UserRepository

Clock = Callable[[], datetime]


class BootstrapFirstAdminHandler:
    def __init__(self, repository: UserRepository, clock: Clock) -> None:
        self.repository = repository
        self.clock = clock

    async def execute(self, command: BootstrapFirstAdminCommand) -> None:
        await self.repository.bootstrap_first_project_admin(
            user_id=command.user_id, project_id=command.project_id, now=self.clock()
        )
