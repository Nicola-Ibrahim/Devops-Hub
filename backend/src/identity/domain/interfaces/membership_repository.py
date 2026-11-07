"""Project membership persistence operations."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from identity.domain.browser_identity import BrowserProjectMember


class ProjectMembershipRepository(Protocol):
    async def set_membership(
        self,
        *,
        actor_id: UUID,
        user_id: UUID,
        project_id: UUID,
        role: str | None,
        now: datetime,
    ) -> None: ...

    async def list_project_members(
        self, *, actor_id: UUID, project_id: UUID
    ) -> tuple[BrowserProjectMember, ...]: ...

    async def lock_project_membership_admin_scope(self, project_id: UUID) -> bool: ...
