from collections.abc import Callable
from datetime import datetime, timedelta

from identity.application.start_password_setup.command import StartPasswordSetupCommand
from identity.domain.interfaces.password_setup_repository import PasswordSetupRepository

Clock = Callable[[], datetime]

DigestSecret = Callable[[str], str]

GenerateSecret = Callable[[], str]


class StartPasswordSetupHandler:
    def __init__(
        self,
        repository: PasswordSetupRepository,
        clock: Clock,
        generate_secret: GenerateSecret,
        digest_secret: DigestSecret,
    ) -> None:
        self.repository = repository
        self.clock = clock
        self.generate_secret = generate_secret
        self.digest_secret = digest_secret

    async def execute(self, command: StartPasswordSetupCommand) -> str:
        secret, now = self.generate_secret(), self.clock()
        await self.repository.issue_password_setup(
            user_id=command.user_id,
            digest=self.digest_secret(secret),
            expires_at=now + timedelta(hours=1),
            actor_id=command.actor_id,
            now=now,
        )
        return secret
