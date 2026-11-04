"""Identity-owned current membership lookup for previously authorized background work."""

from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from identity.infra.persistence.models import InternalUserRow, ProjectMembershipRow, ProjectRow


async def resource_request_role(
    session: AsyncSession, user_id: UUID, project_id: UUID
) -> Literal["developer", "admin"] | None:
    # Same project -> user -> membership hierarchy as internal administration.
    if (
        await session.scalar(
            select(ProjectRow.id).where(ProjectRow.id == project_id).with_for_update(read=True)
        )
        is None
    ):
        return None
    user = await session.scalar(
        select(InternalUserRow).where(InternalUserRow.id == user_id).with_for_update(read=True)
    )
    if user is None or not user.active:
        return None
    role = await session.scalar(
        select(ProjectMembershipRow.role)
        .where(
            ProjectMembershipRow.user_id == user_id, ProjectMembershipRow.project_id == project_id
        )
        .with_for_update(read=True)
    )
    return cast(Literal["developer", "admin"], role) if role in {"developer", "admin"} else None
