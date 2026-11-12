from collections.abc import Callable
from datetime import datetime

from identity.application.manage_project_membership.command import (
    ManageProjectMembershipCommand,
    SetProjectMembershipCommand,
)
from identity.application.shared.session_security import (
    AuthorizeBrowserMutationCommand,
    AuthorizeBrowserMutationHandler,
    DigestSecret,
)
from identity.domain.aggregates.project_membership import ProjectMembership
from identity.domain.interfaces.membership_repository import ProjectMembershipRepository
from identity.domain.interfaces.membership_session_repository import MembershipSessionRepository
from identity.domain.value_objects.project_role import ProjectRole

Clock = Callable[[], datetime]


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
        membership = (
            ProjectMembership(command.user_id, command.project_id, ProjectRole.parse(command.role))
            if command.role is not None
            else None
        )
        role = membership.role.value if membership is not None else None
        await self.repository.set_membership(
            actor_id=principal.user_id,
            user_id=command.user_id,
            project_id=command.project_id,
            role=role,
            now=self.clock(),
        )


class SetProjectMembershipHandler:
    def __init__(self, repository: ProjectMembershipRepository, clock: Clock) -> None:
        self.repository = repository
        self.clock = clock

    async def execute(self, command: SetProjectMembershipCommand) -> None:
        membership = (
            ProjectMembership(command.user_id, command.project_id, ProjectRole.parse(command.role))
            if command.role is not None
            else None
        )
        role = membership.role.value if membership is not None else None
        await self.repository.set_membership(
            actor_id=command.actor_id,
            user_id=command.user_id,
            project_id=command.project_id,
            role=role,
            now=self.clock(),
        )
