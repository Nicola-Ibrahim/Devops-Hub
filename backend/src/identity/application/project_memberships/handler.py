"""Project membership administration use cases for internal identity."""

from collections.abc import Callable
from datetime import datetime

from identity.application.browser_sessions.command import AuthorizeBrowserMutationCommand
from identity.application.browser_sessions.handler import (
    AuthorizeBrowserMutationHandler,
    DigestSecret,
)
from identity.application.project_memberships.command import (
    ManageProjectMembershipCommand,
    SetProjectMembershipCommand,
)
from identity.application.project_memberships.query import ListProjectMembersQuery
from identity.domain.browser_identity import BrowserProjectMember
from identity.domain.interfaces.membership_repository import ProjectMembershipRepository
from identity.domain.interfaces.membership_session_repository import MembershipSessionRepository
from identity.domain.value_objects.project_role import ProjectRole

Clock = Callable[[], datetime]


class SetProjectMembershipHandler:
    def __init__(self, repository: ProjectMembershipRepository, clock: Clock) -> None:
        self.repository = repository
        self.clock = clock

    async def execute(self, command: SetProjectMembershipCommand) -> None:
        role = ProjectRole.parse(command.role).value if command.role is not None else None
        await self.repository.set_membership(
            actor_id=command.actor_id,
            user_id=command.user_id,
            project_id=command.project_id,
            role=role,
            now=self.clock(),
        )


class ListProjectMembersHandler:
    def __init__(self, repository: ProjectMembershipRepository) -> None:
        self.repository = repository

    async def execute(self, query: ListProjectMembersQuery) -> tuple[BrowserProjectMember, ...]:
        return await self.repository.list_project_members(
            actor_id=query.actor_id, project_id=query.project_id
        )


class ManageProjectMembershipHandler:
    def __init__(
        self,
        repository: MembershipSessionRepository,
        clock: Clock,
        digest_secret: DigestSecret,
        allowed_origins: tuple[str, ...],
    ) -> None:
        self.repository = repository
        self.clock = clock
        self.authorize = AuthorizeBrowserMutationHandler(
            repository, clock, digest_secret, allowed_origins
        )

    async def execute(self, command: ManageProjectMembershipCommand) -> None:
        await self.repository.lock_project_membership_admin_scope(command.project_id)
        principal = await self.authorize.execute(
            AuthorizeBrowserMutationCommand(
                command.session_token, command.csrf_token, command.origin
            )
        )
        role = ProjectRole.parse(command.role).value if command.role is not None else None
        await self.repository.set_membership(
            actor_id=principal.user_id,
            user_id=command.user_id,
            project_id=command.project_id,
            role=role,
            now=self.clock(),
        )
