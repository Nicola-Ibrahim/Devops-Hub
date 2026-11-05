"""Project membership administration use cases for internal identity."""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from identity.application.browser_sessions import (
    BrowserSessionService,
    DigestSecret,
    GenerateSecret,
)
from identity.domain.browser_errors import BrowserAuthenticationRejected
from identity.domain.browser_identity import (
    BrowserIdentityRepository,
    BrowserProjectMember,
)

Clock = Callable[[], datetime]


class SetProjectMembership:
    def __init__(self, repository: BrowserIdentityRepository, clock: Clock) -> None:
        self.repository = repository
        self.clock = clock

    async def execute(
        self, actor_id: UUID, user_id: UUID, project_id: UUID, role: str | None
    ) -> None:
        await self.repository.set_membership(
            actor_id=actor_id,
            user_id=user_id,
            project_id=project_id,
            role=role,
            now=self.clock(),
        )


class ListProjectMembers:
    def __init__(
        self,
        repository: BrowserIdentityRepository,
        clock: Clock,
        digest_secret: DigestSecret,
    ) -> None:
        self.repository = repository
        self.clock = clock
        self.digest_secret = digest_secret

    async def execute(
        self, session_token: str, project_id: UUID
    ) -> tuple[BrowserProjectMember, ...]:
        principal = await self.repository.authorize_browser_operation(
            self.digest_secret(session_token), project_id, self.clock()
        )
        if principal is None:
            raise BrowserAuthenticationRejected()
        return await self.repository.list_project_members(
            actor_id=principal.user_id, project_id=project_id
        )


class ManageProjectMembership:
    def __init__(
        self,
        repository: BrowserIdentityRepository,
        clock: Clock,
        digest_secret: DigestSecret,
        generate_secret: GenerateSecret,
        allowed_origins: tuple[str, ...],
    ) -> None:
        self.repository = repository
        self.clock = clock
        self.sessions = BrowserSessionService(
            repository, clock, digest_secret, generate_secret, allowed_origins
        )

    async def execute(
        self,
        session_token: str,
        project_id: UUID,
        user_id: UUID,
        role: str | None,
        csrf_token: str,
        origin: str | None,
    ) -> None:
        await self.repository.lock_project_membership_admin_scope(project_id)
        principal = await self.sessions.authorize_mutation(session_token, csrf_token, origin)
        await self.repository.set_membership(
            actor_id=principal.user_id,
            user_id=user_id,
            project_id=project_id,
            role=role,
            now=self.clock(),
        )
