"""SQLAlchemy implementation of identity's API token repository."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from identity.application.errors import IdentityUnavailable
from identity.domain.credentials import ApiTokenAuthenticationDetails
from identity.domain.records import ApiTokenAuditEvent, ApiTokenStatus, ProjectMembershipStatus
from identity.infra.persistence.models import (
    ApiAccessTokenRow,
    InternalUserRow,
    ProjectMembershipRow,
    ProjectRow,
)
from shared.infra.persistence.audit import AuditEvent


class SQLAlchemyApiTokenRepository:
    """Identity persistence bound to an operation-scoped session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_token_credential(self, digest: str) -> ApiTokenAuthenticationDetails | None:
        try:
            row = (
                await self._session.execute(
                    select(ApiAccessTokenRow, InternalUserRow.active, ProjectMembershipRow.role)
                    .join(InternalUserRow, InternalUserRow.id == ApiAccessTokenRow.user_id)
                    .outerjoin(
                        ProjectMembershipRow,
                        (ProjectMembershipRow.user_id == ApiAccessTokenRow.user_id)
                        & (ProjectMembershipRow.project_id == ApiAccessTokenRow.project_id),
                    )
                    .where(ApiAccessTokenRow.digest == digest)
                )
            ).one_or_none()
            if row is None:
                return None
            token, active, role = row
            return ApiTokenAuthenticationDetails(
                token_id=token.id,
                user_id=token.user_id,
                project_id=token.project_id,
                role=role,
                scopes=tuple(token.scopes),
                user_active=active,
                expires_at=token.expires_at,
                revoked_at=token.revoked_at,
            )
        except SQLAlchemyError as exc:
            raise IdentityUnavailable() from exc

    async def ensure_developer_membership(
        self, *, user_name: str, project_name: str, new_role: str
    ) -> ProjectMembershipStatus:
        try:
            user = await self._session.scalar(
                select(InternalUserRow).where(InternalUserRow.name == user_name)
            )
            if user is None:
                user = InternalUserRow(name=user_name)
                self._session.add(user)
                await self._session.flush()
            project = await self._session.scalar(
                select(ProjectRow).where(ProjectRow.name == project_name)
            )
            if project is None:
                project = ProjectRow(name=project_name)
                self._session.add(project)
                await self._session.flush()
            membership = await self._session.get(ProjectMembershipRow, (user.id, project.id))
            if membership is None:
                self._session.add(
                    ProjectMembershipRow(user_id=user.id, project_id=project.id, role=new_role)
                )
            return ProjectMembershipStatus(
                user_id=user.id, project_id=project.id, user_active=user.active
            )
        except SQLAlchemyError as exc:
            raise IdentityUnavailable() from exc

    async def insert_api_token(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        digest: str,
        scopes: tuple[str, ...],
        expires_at: datetime,
        created_at: datetime,
    ) -> UUID:
        try:
            token = ApiAccessTokenRow(
                user_id=user_id,
                project_id=project_id,
                digest=digest,
                scopes=list(scopes),
                created_at=created_at,
                expires_at=expires_at,
                revoked_at=None,
            )
            self._session.add(token)
            await self._session.flush()
            return token.id
        except SQLAlchemyError as exc:
            raise IdentityUnavailable() from exc

    async def record_token_audit(self, event: ApiTokenAuditEvent) -> None:
        try:
            self._session.add(
                AuditEvent(
                    actor_id=event.actor_id,
                    project_id=event.project_id,
                    action=event.action,
                    outcome=event.outcome,
                    request_id=event.request_id,
                )
            )
        except SQLAlchemyError as exc:
            raise IdentityUnavailable() from exc

    async def find_api_token(self, token_id: UUID) -> ApiTokenStatus | None:
        try:
            token = await self._session.get(ApiAccessTokenRow, token_id)
            if token is None:
                return None
            return ApiTokenStatus(token.id, token.user_id, token.project_id, token.revoked_at)
        except SQLAlchemyError as exc:
            raise IdentityUnavailable() from exc

    async def revoke_api_token(self, token_id: UUID, revoked_at: datetime) -> None:
        try:
            token = await self._session.get(ApiAccessTokenRow, token_id)
            if token is not None:
                token.revoked_at = revoked_at
        except SQLAlchemyError as exc:
            raise IdentityUnavailable() from exc
