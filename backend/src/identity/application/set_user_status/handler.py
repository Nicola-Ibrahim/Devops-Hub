from collections.abc import Callable
from datetime import datetime

from identity.application.set_user_status.command import SetUserStatusCommand
from identity.domain.interfaces.user_repository import UserRepository

Clock = Callable[[], datetime]


class SetUserStatusHandler:
    def __init__(self, repository: UserRepository, clock: Clock) -> None:
        self.repository = repository
        self.clock = clock

    async def execute(self, command: SetUserStatusCommand) -> None:
        await self.repository.set_user_active(
            actor_id=command.actor_id,
            user_id=command.user_id,
            active=command.active,
            now=self.clock(),
        )
