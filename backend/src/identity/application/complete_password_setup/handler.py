import asyncio
from collections.abc import Callable
from datetime import datetime

from identity.application.complete_password_setup.command import CompletePasswordSetupCommand
from identity.application.shared.ports import PasswordHasher
from identity.domain.browser_credentials import validate_password
from identity.domain.interfaces.password_setup_repository import PasswordSetupRepository

Clock = Callable[[], datetime]

DigestSecret = Callable[[str], str]


class CompletePasswordSetupHandler:
    def __init__(
        self,
        repository: PasswordSetupRepository,
        passwords: PasswordHasher,
        clock: Clock,
        digest_secret: DigestSecret,
    ) -> None:
        self.repository = repository
        self.passwords = passwords
        self.clock = clock
        self.digest_secret = digest_secret

    async def execute(self, command: CompletePasswordSetupCommand) -> bool:
        validate_password(command.new_password)
        encoded = await asyncio.to_thread(self.passwords.hash, command.new_password)
        return await self.repository.consume_password_setup(
            digest=self.digest_secret(command.secret), password_hash=encoded, now=self.clock()
        )
