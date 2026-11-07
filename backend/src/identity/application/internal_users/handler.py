"""Internal user-account and password setup use cases."""

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import UUID

from identity.application.internal_users.command import (
    BootstrapFirstProjectAdminCommand,
    ConsumePasswordSetupCommand,
    CreateInternalUserCommand,
    IssuePasswordSetupCommand,
    SetInternalUserActiveCommand,
)
from identity.application.shared.ports import PasswordHasher
from identity.domain.browser_credentials import validate_password
from identity.domain.interfaces.account_repository import BrowserAccountRepository
from identity.domain.interfaces.password_setup_repository import PasswordSetupRepository
from identity.domain.value_objects.user_name import UserName

Clock = Callable[[], datetime]
DigestSecret = Callable[[str], str]
GenerateSecret = Callable[[], str]


class CreateInternalUserHandler:
    def __init__(
        self, repository: BrowserAccountRepository, passwords: PasswordHasher, clock: Clock
    ) -> None:
        self.repository = repository
        self.passwords = passwords
        self.clock = clock

    async def execute(self, command: CreateInternalUserCommand) -> UUID:
        name = UserName.parse(command.user_name).value
        validate_password(command.password)
        encoded = await asyncio.to_thread(self.passwords.hash, command.password)
        return await self.repository.create_user(name, encoded, command.actor_id, self.clock())


class BootstrapFirstProjectAdminHandler:
    def __init__(self, repository: BrowserAccountRepository, clock: Clock) -> None:
        self.repository = repository
        self.clock = clock

    async def execute(self, command: BootstrapFirstProjectAdminCommand) -> None:
        await self.repository.bootstrap_first_project_admin(
            user_id=command.user_id, project_id=command.project_id, now=self.clock()
        )


class SetInternalUserActiveHandler:
    def __init__(self, repository: BrowserAccountRepository, clock: Clock) -> None:
        self.repository = repository
        self.clock = clock

    async def execute(self, command: SetInternalUserActiveCommand) -> None:
        await self.repository.set_user_active(
            actor_id=command.actor_id,
            user_id=command.user_id,
            active=command.active,
            now=self.clock(),
        )


class IssuePasswordSetupHandler:
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

    async def execute(self, command: IssuePasswordSetupCommand) -> str:
        secret, now = self.generate_secret(), self.clock()
        await self.repository.issue_password_setup(
            user_id=command.user_id,
            digest=self.digest_secret(secret),
            expires_at=now + timedelta(hours=1),
            actor_id=command.actor_id,
            now=now,
        )
        return secret


class ConsumePasswordSetupHandler:
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

    async def execute(self, command: ConsumePasswordSetupCommand) -> bool:
        validate_password(command.new_password)
        encoded = await asyncio.to_thread(self.passwords.hash, command.new_password)
        return await self.repository.consume_password_setup(
            digest=self.digest_secret(command.secret), password_hash=encoded, now=self.clock()
        )
