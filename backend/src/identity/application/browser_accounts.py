"""Internal user-account and password setup use cases."""

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import UUID

from identity.application.ports import PasswordHasher
from identity.domain.browser_credentials import normalize_user_name, validate_password
from identity.domain.browser_identity import BrowserIdentityRepository

Clock = Callable[[], datetime]
DigestSecret = Callable[[str], str]
GenerateSecret = Callable[[], str]


class CreateInternalUser:
    def __init__(
        self, repository: BrowserIdentityRepository, passwords: PasswordHasher, clock: Clock
    ) -> None:
        self.repository = repository
        self.passwords = passwords
        self.clock = clock

    async def execute(self, user_name: str, password: str, actor_id: UUID | None) -> UUID:
        name = normalize_user_name(user_name)
        validate_password(password)
        encoded = await asyncio.to_thread(self.passwords.hash, password)
        return await self.repository.create_user(name, encoded, actor_id, self.clock())


class BootstrapFirstProjectAdmin:
    def __init__(self, repository: BrowserIdentityRepository, clock: Clock) -> None:
        self.repository = repository
        self.clock = clock

    async def execute(self, user_id: UUID, project_id: UUID) -> None:
        await self.repository.bootstrap_first_project_admin(
            user_id=user_id, project_id=project_id, now=self.clock()
        )


class SetInternalUserActive:
    def __init__(self, repository: BrowserIdentityRepository, clock: Clock) -> None:
        self.repository = repository
        self.clock = clock

    async def execute(self, actor_id: UUID, user_id: UUID, active: bool) -> None:
        await self.repository.set_user_active(
            actor_id=actor_id, user_id=user_id, active=active, now=self.clock()
        )


class IssuePasswordSetup:
    def __init__(
        self,
        repository: BrowserIdentityRepository,
        clock: Clock,
        generate_secret: GenerateSecret,
        digest_secret: DigestSecret,
    ) -> None:
        self.repository = repository
        self.clock = clock
        self.generate_secret = generate_secret
        self.digest_secret = digest_secret

    async def execute(self, user_id: UUID, actor_id: UUID) -> str:
        secret, now = self.generate_secret(), self.clock()
        await self.repository.issue_password_setup(
            user_id=user_id,
            digest=self.digest_secret(secret),
            expires_at=now + timedelta(hours=1),
            actor_id=actor_id,
            now=now,
        )
        return secret


class ConsumePasswordSetup:
    def __init__(
        self,
        repository: BrowserIdentityRepository,
        passwords: PasswordHasher,
        clock: Clock,
        digest_secret: DigestSecret,
    ) -> None:
        self.repository = repository
        self.passwords = passwords
        self.clock = clock
        self.digest_secret = digest_secret

    async def execute(self, secret: str, new_password: str) -> bool:
        validate_password(new_password)
        encoded = await asyncio.to_thread(self.passwords.hash, new_password)
        return await self.repository.consume_password_setup(
            digest=self.digest_secret(secret), password_hash=encoded, now=self.clock()
        )
