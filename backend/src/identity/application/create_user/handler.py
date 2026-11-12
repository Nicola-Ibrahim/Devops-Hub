import asyncio
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from identity.application.create_user.command import CreateUserCommand
from identity.application.shared.ports import PasswordHasher
from identity.domain.browser_credentials import validate_password
from identity.domain.interfaces.user_repository import UserRepository
from identity.domain.value_objects.user_name import UserName

Clock = Callable[[], datetime]


class CreateUserHandler:
    def __init__(self, repository: UserRepository, passwords: PasswordHasher, clock: Clock) -> None:
        self.repository = repository
        self.passwords = passwords
        self.clock = clock

    async def execute(self, command: CreateUserCommand) -> UUID:
        name = UserName.parse(command.user_name).value
        validate_password(command.password)
        encoded = await asyncio.to_thread(self.passwords.hash, command.password)
        return await self.repository.create_user(name, encoded, command.actor_id, self.clock())
