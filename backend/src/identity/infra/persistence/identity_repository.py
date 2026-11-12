"""SQLAlchemy adapter for browser credentials, sessions and account administration."""

import hmac
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from identity.application.shared.principal import principal_for_project
from identity.domain.aggregates.session import Session
from identity.domain.browser_errors import BrowserAuthenticationRejected
from identity.domain.errors import IdentityValidationError
from identity.domain.interfaces.membership_repository import ProjectMembershipRepository
from identity.domain.interfaces.password_setup_repository import PasswordSetupRepository
from identity.domain.interfaces.session_repository import SessionRepository
from identity.domain.interfaces.user_repository import UserRepository
from identity.domain.records import (
    AccountCredentials,
    MembershipDetails,
    ProjectMemberDetails,
    SessionPrincipal,
)
from identity.domain.value_objects.session_expiry import SessionExpiry
from identity.infra.persistence.models import (
    BrowserLoginThrottleRow,
    BrowserSessionRow,
    IdentityActivityRow,
    InternalUserRow,
    PasswordSetupRow,
    ProjectMembershipRow,
    ProjectRow,
)

_THROTTLE_WINDOW = timedelta(minutes=15)
_MAX_FAILURES = 6
_LOCK_TIME = timedelta(minutes=15)
_IDLE_WINDOW = timedelta(minutes=30)


class SQLAlchemyIdentityRepository(
    UserRepository,
    SessionRepository,
    ProjectMembershipRepository,
    PasswordSetupRepository,
):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _domain_session(row: BrowserSessionRow) -> Session:
        return Session(
            row.id,
            row.user_id,
            row.created_at,
            row.last_seen_at,
            SessionExpiry(row.idle_expires_at, row.absolute_expires_at),
            row.revoked_at,
            row.credential_version,
        )

    async def _memberships(self, user_id: UUID) -> tuple[MembershipDetails, ...]:
        statement = (
            select(ProjectMembershipRow.project_id, ProjectRow.name, ProjectMembershipRow.role)
            .join(ProjectRow, ProjectRow.id == ProjectMembershipRow.project_id)
            .where(ProjectMembershipRow.user_id == user_id)
            .order_by(ProjectRow.name)
        )
        rows = (await self._session.execute(statement)).all()
        return tuple(MembershipDetails(project_id, name, role) for project_id, name, role in rows)

    async def _lock_user_projects(
        self, user_id: UUID, additional_project_ids: tuple[UUID, ...] = ()
    ) -> tuple[UUID, ...] | None:
        """Lock the known membership scope in UUID order before user/session rows."""
        initial = tuple(
            (
                await self._session.scalars(
                    select(ProjectMembershipRow.project_id)
                    .where(ProjectMembershipRow.user_id == user_id)
                    .order_by(ProjectMembershipRow.project_id)
                )
            ).all()
        )
        project_ids = tuple(sorted(set(initial).union(additional_project_ids)))
        if project_ids:
            locked_projects = await self._session.scalars(
                select(ProjectRow)
                .where(ProjectRow.id.in_(project_ids))
                .order_by(ProjectRow.id)
                .with_for_update()
            )
            locked_projects.all()
        current = tuple(
            (
                await self._session.scalars(
                    select(ProjectMembershipRow.project_id)
                    .where(ProjectMembershipRow.user_id == user_id)
                    .order_by(ProjectMembershipRow.project_id)
                )
            ).all()
        )
        # A membership added on a project outside the initial lock set means the
        # caller must retry in a fresh transaction to preserve the global order.
        if not set(current).issubset(project_ids):
            return None
        return current

    async def find_login_account(self, user_name: str) -> AccountCredentials | None:
        user = await self._session.scalar(
            select(InternalUserRow).where(InternalUserRow.name == user_name)
        )
        if user is None or user.password_hash is None:
            return None
        return AccountCredentials(
            user_id=user.id,
            user_name=user.name,
            password_hash=user.password_hash,
            credential_version=user.credential_version,
            active=user.active,
            memberships=await self._memberships(user.id),
        )

    async def complete_login(
        self,
        *,
        user_name: str,
        username_digest: str,
        expected_version: int | None,
        accepted: bool,
        token_digest: str,
        csrf_digest: str,
        now: datetime,
    ) -> tuple[SessionPrincipal, UUID, datetime] | None:
        user = await self._session.scalar(
            select(InternalUserRow).where(InternalUserRow.name == user_name).with_for_update()
        )
        # Do not create an unbounded persistent bucket for arbitrary unknown names.
        if user is None:
            return None
        await self._session.execute(
            insert(BrowserLoginThrottleRow)
            .values(username_digest=username_digest, failures=0, window_started_at=now)
            .on_conflict_do_nothing(index_elements=[BrowserLoginThrottleRow.username_digest])
        )
        throttle = await self._session.scalar(
            select(BrowserLoginThrottleRow)
            .where(BrowserLoginThrottleRow.username_digest == username_digest)
            .with_for_update()
        )
        assert throttle is not None
        locked = throttle.locked_until is not None and throttle.locked_until > now
        if locked:
            return None
        if not accepted or not user.active or user.password_hash is None:
            if throttle.window_started_at + _THROTTLE_WINDOW <= now:
                throttle.failures = 0
                throttle.window_started_at = now
                throttle.locked_until = None
            throttle.failures += 1
            if throttle.failures >= _MAX_FAILURES:
                throttle.locked_until = now + _LOCK_TIME
            await self._record_activity(None, user.id, None, "login_rejected", "failed", now)
            return None
        if user.credential_version != expected_version:
            return None
        throttle.failures = 0
        throttle.window_started_at = now
        throttle.locked_until = None
        idle_expires = now + _IDLE_WINDOW
        absolute_expires = now + timedelta(hours=8)
        session = BrowserSessionRow(
            user_id=user.id,
            token_digest=token_digest,
            csrf_digest=csrf_digest,
            credential_version=user.credential_version,
            created_at=now,
            last_seen_at=now,
            idle_expires_at=idle_expires,
            absolute_expires_at=absolute_expires,
        )
        self._session.add(session)
        await self._session.flush()
        await self._record_activity(user.id, user.id, None, "browser_login", "succeeded", now)
        memberships = await self._memberships(user.id)
        principal = principal_for_project(
            user_id=user.id,
            user_name=user.name,
            session_id=session.id,
            memberships=memberships,
            project_id=None,
            csrf_token="",
        )
        return principal, session.id, absolute_expires

    async def authenticate_session(
        self,
        *,
        token_digest: str,
        project_id: UUID | None,
        now: datetime,
    ) -> tuple[SessionPrincipal, str] | None:
        row = await self._session.scalar(
            select(BrowserSessionRow).where(BrowserSessionRow.token_digest == token_digest)
        )
        if row is None:
            return None
        user = await self._session.get(InternalUserRow, row.user_id)
        if (
            user is None
            or not self._domain_session(row).accepts(
                now=now,
                user_active=user.active,
                credential_version=user.credential_version,
            )
            or row.credential_version != user.credential_version
        ):
            return None
        memberships = await self._memberships(user.id)
        selected_project_id = project_id if project_id is not None else row.selected_project_id
        if selected_project_id is not None and not any(
            item.project_id == selected_project_id for item in memberships
        ):
            return None
        if now - row.last_seen_at >= timedelta(minutes=5):
            row.last_seen_at = now
            row.idle_expires_at = min(now + _IDLE_WINDOW, row.absolute_expires_at)
        principal = principal_for_project(
            user_id=user.id,
            user_name=user.name,
            session_id=row.id,
            memberships=memberships,
            project_id=selected_project_id,
            csrf_token="",
        )
        return principal, row.csrf_digest

    async def authorize_browser_operation(
        self,
        token_digest: str,
        project_id: UUID | None,
        now: datetime,
        lock_for_mutation: bool = False,
    ) -> SessionPrincipal | None:
        # Discover the lock keys without taking a lock. Shared operations then use
        # project -> user -> session, matching membership and account administration.
        snapshot = await self._session.scalar(
            select(BrowserSessionRow).where(BrowserSessionRow.token_digest == token_digest)
        )
        if snapshot is None:
            return None
        selected = project_id if project_id is not None else snapshot.selected_project_id
        project_ids = await self._lock_user_projects(
            snapshot.user_id, (selected,) if selected is not None else ()
        )
        if project_ids is None or (selected is not None and selected not in project_ids):
            return None
        user_statement = select(InternalUserRow).where(InternalUserRow.id == snapshot.user_id)
        user_statement = (
            user_statement.with_for_update()
            if lock_for_mutation
            else user_statement.with_for_update(read=True)
        )
        user = await self._session.scalar(user_statement)
        row = await self._session.scalar(
            select(BrowserSessionRow)
            .where(
                BrowserSessionRow.id == snapshot.id,
                BrowserSessionRow.token_digest == token_digest,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if (
            row is None
            or row.user_id != snapshot.user_id
            or user is None
            or not user.active
            or user.credential_version != row.credential_version
        ):
            return None
        current_selected = project_id if project_id is not None else row.selected_project_id
        # The selected project may have changed while acquiring locks. Do not use
        # a lock acquired for the previous project to authorize the new selection.
        if current_selected != selected:
            return None
        if not self._domain_session(row).accepts(
            now=now,
            user_active=user.active,
            credential_version=user.credential_version,
        ):
            return None
        if selected is not None:
            role = await self._session.scalar(
                select(ProjectMembershipRow.role).where(
                    ProjectMembershipRow.user_id == user.id,
                    ProjectMembershipRow.project_id == selected,
                )
            )
            if role is None:
                return None
        memberships = await self._memberships(user.id)
        if now - row.last_seen_at >= timedelta(minutes=5):
            row.last_seen_at = now
            row.idle_expires_at = min(now + _IDLE_WINDOW, row.absolute_expires_at)
        return principal_for_project(
            user_id=user.id,
            user_name=user.name,
            session_id=row.id,
            memberships=memberships,
            project_id=selected,
            csrf_token="",
        )

    async def rotate_csrf(self, token_digest: str, csrf_digest: str, now: datetime) -> bool:
        row = await self._session.scalar(
            select(BrowserSessionRow)
            .where(BrowserSessionRow.token_digest == token_digest)
            .with_for_update()
        )
        if row is None or row.revoked_at is not None or row.absolute_expires_at <= now:
            return False
        row.csrf_digest = csrf_digest
        return True

    async def validate_csrf(self, token_digest: str, csrf_digest: str) -> bool:
        stored = await self._session.scalar(
            select(BrowserSessionRow.csrf_digest).where(
                BrowserSessionRow.token_digest == token_digest,
                BrowserSessionRow.revoked_at.is_(None),
            )
        )
        return stored is not None and hmac.compare_digest(stored, csrf_digest)

    async def select_project(
        self,
        *,
        token_digest: str,
        project_id: UUID,
        now: datetime,
    ) -> SessionPrincipal | None:
        snapshot = await self._session.scalar(
            select(BrowserSessionRow).where(BrowserSessionRow.token_digest == token_digest)
        )
        if snapshot is None:
            return None
        if not await self._session.scalar(
            select(ProjectMembershipRow.role).where(
                ProjectMembershipRow.user_id == snapshot.user_id,
                ProjectMembershipRow.project_id == project_id,
            )
        ):
            return None
        project_ids = await self._lock_user_projects(snapshot.user_id, (project_id,))
        if project_ids is None or project_id not in project_ids:
            return None
        user = await self._session.scalar(
            select(InternalUserRow).where(InternalUserRow.id == snapshot.user_id).with_for_update()
        )
        row = await self._session.scalar(
            select(BrowserSessionRow)
            .where(
                BrowserSessionRow.id == snapshot.id,
                BrowserSessionRow.token_digest == token_digest,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if (
            row is None
            or row.user_id != snapshot.user_id
            or user is None
            or not self._domain_session(row).accepts(
                now=now,
                user_active=user.active,
                credential_version=user.credential_version,
            )
            or row.credential_version != user.credential_version
        ):
            return None
        role = await self._session.scalar(
            select(ProjectMembershipRow.role).where(
                ProjectMembershipRow.user_id == user.id,
                ProjectMembershipRow.project_id == project_id,
            )
        )
        if role is None:
            return None
        memberships = await self._memberships(user.id)
        row.selected_project_id = project_id
        row.last_seen_at = now
        row.idle_expires_at = min(now + _IDLE_WINDOW, row.absolute_expires_at)
        return principal_for_project(
            user_id=user.id,
            user_name=user.name,
            session_id=row.id,
            memberships=memberships,
            project_id=project_id,
            csrf_token="",
        )

    async def logout(self, token_digest: str, now: datetime) -> None:
        row = await self._session.scalar(
            select(BrowserSessionRow)
            .where(BrowserSessionRow.token_digest == token_digest)
            .with_for_update()
        )
        if row is not None and row.revoked_at is None:
            row.revoked_at = now
            await self._record_activity(
                row.user_id,
                row.user_id,
                row.selected_project_id,
                "browser_logout",
                "succeeded",
                now,
            )

    async def logout_all(self, user_id: UUID, now: datetime) -> int:
        result = await self._session.execute(
            update(BrowserSessionRow)
            .where(BrowserSessionRow.user_id == user_id, BrowserSessionRow.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        count = int(getattr(result, "rowcount", 0) or 0)
        await self._record_activity(
            user_id, user_id, None, "all_browser_sessions_revoked", "succeeded", now
        )
        return count

    async def list_sessions(
        self, user_id: UUID, current_session_id: UUID, now: datetime
    ) -> tuple[Session, ...]:
        rows = (
            await self._session.scalars(
                select(BrowserSessionRow)
                .where(
                    BrowserSessionRow.user_id == user_id,
                    BrowserSessionRow.revoked_at.is_(None),
                    BrowserSessionRow.idle_expires_at > now,
                    BrowserSessionRow.absolute_expires_at > now,
                )
                .order_by(BrowserSessionRow.created_at.desc())
            )
        ).all()
        return tuple(
            Session(
                row.id,
                row.user_id,
                row.created_at,
                row.last_seen_at,
                SessionExpiry(row.idle_expires_at, row.absolute_expires_at),
                row.revoked_at,
                row.credential_version,
            )
            for row in rows
        )

    async def revoke_session(self, user_id: UUID, session_id: UUID, now: datetime) -> bool:
        row = await self._session.scalar(
            select(BrowserSessionRow)
            .where(BrowserSessionRow.user_id == user_id, BrowserSessionRow.id == session_id)
            .with_for_update()
        )
        if row is None or row.revoked_at is not None:
            return False
        row.revoked_at = now
        await self._record_activity(
            user_id, user_id, row.selected_project_id, "browser_session_revoked", "succeeded", now
        )
        return True

    async def change_password(
        self,
        *,
        user_id: UUID,
        expected_version: int,
        password_hash: str,
        now: datetime,
    ) -> bool:
        user = await self._session.scalar(
            select(InternalUserRow).where(InternalUserRow.id == user_id).with_for_update()
        )
        if user is None or not user.active or user.credential_version != expected_version:
            return False
        user.password_hash = password_hash
        user.credential_version += 1
        await self._session.execute(
            update(BrowserSessionRow)
            .where(BrowserSessionRow.user_id == user_id, BrowserSessionRow.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self._record_activity(user_id, user_id, None, "password_changed", "succeeded", now)
        return True

    async def create_user(
        self, user_name: str, password_hash: str, actor_id: UUID | None, now: datetime
    ) -> UUID:
        user = InternalUserRow(
            name=user_name, active=True, password_hash=password_hash, created_at=now
        )
        self._session.add(user)
        await self._session.flush()
        await self._record_activity(actor_id, user.id, None, "user_created", "succeeded", now)
        return user.id

    async def set_membership(
        self,
        *,
        actor_id: UUID,
        user_id: UUID,
        project_id: UUID,
        role: str | None,
        now: datetime,
    ) -> None:
        if role not in {None, "developer", "admin"}:
            raise IdentityValidationError("Unsupported project role")
        project_exists = await self.lock_project_membership_admin_scope(project_id)
        target = await self._session.scalar(
            select(InternalUserRow).where(InternalUserRow.id == user_id).with_for_update(read=True)
        )
        if not project_exists or target is None or not target.active:
            raise IdentityValidationError("Active user and project are required")
        actor_role = await self._session.scalar(
            select(ProjectMembershipRow.role).where(
                ProjectMembershipRow.user_id == actor_id,
                ProjectMembershipRow.project_id == project_id,
            )
        )
        if actor_role != "admin":
            raise BrowserAuthenticationRejected()
        if actor_id == user_id and role in {None, "developer"}:
            raise IdentityValidationError("Ask another project administrator to change your role")
        row = await self._session.get(
            ProjectMembershipRow, (user_id, project_id), with_for_update=True
        )
        if role in {None, "developer"} and row is not None and row.role == "admin":
            admins = await self._session.scalar(
                select(func.count())
                .select_from(ProjectMembershipRow)
                .where(
                    ProjectMembershipRow.project_id == project_id,
                    ProjectMembershipRow.role == "admin",
                )
            )
            if admins is not None and admins <= 1:
                raise IdentityValidationError("A project must retain at least one administrator")
        if role is None:
            if row is not None:
                await self._session.delete(row)
        elif row is None:
            self._session.add(
                ProjectMembershipRow(user_id=user_id, project_id=project_id, role=role)
            )
        else:
            row.role = role
        await self._record_activity(
            actor_id, user_id, project_id, "membership_changed", "succeeded", now
        )

    async def lock_project_membership_admin_scope(self, project_id: UUID) -> bool:
        project = await self._session.scalar(
            select(ProjectRow).where(ProjectRow.id == project_id).with_for_update()
        )
        if project is None:
            return False
        return True

    async def bootstrap_first_project_admin(
        self, *, user_id: UUID, project_id: UUID, now: datetime
    ) -> None:
        project = await self._session.scalar(
            select(ProjectRow).where(ProjectRow.id == project_id).with_for_update()
        )
        user = await self._session.scalar(
            select(InternalUserRow).where(InternalUserRow.id == user_id).with_for_update()
        )
        if project is None or user is None or not user.active:
            raise IdentityValidationError("Active user and project are required")
        admin_count = await self._session.scalar(
            select(func.count())
            .select_from(ProjectMembershipRow)
            .where(
                ProjectMembershipRow.project_id == project_id,
                ProjectMembershipRow.role == "admin",
            )
        )
        if admin_count:
            raise IdentityValidationError("Project already has an administrator")
        membership = await self._session.get(ProjectMembershipRow, (user_id, project_id))
        if membership is None:
            self._session.add(
                ProjectMembershipRow(user_id=user_id, project_id=project_id, role="admin")
            )
        else:
            membership.role = "admin"
        await self._record_activity(
            None, user_id, project_id, "first_project_admin_bootstrapped", "succeeded", now
        )

    async def list_project_members(
        self, *, actor_id: UUID, project_id: UUID
    ) -> tuple[ProjectMemberDetails, ...]:
        actor_role = await self._session.scalar(
            select(ProjectMembershipRow.role).where(
                ProjectMembershipRow.user_id == actor_id,
                ProjectMembershipRow.project_id == project_id,
            )
        )
        if actor_role != "admin":
            raise BrowserAuthenticationRejected()
        rows = (
            await self._session.execute(
                select(
                    InternalUserRow.id,
                    InternalUserRow.name,
                    ProjectMembershipRow.role,
                    InternalUserRow.active,
                )
                .join(InternalUserRow, InternalUserRow.id == ProjectMembershipRow.user_id)
                .where(ProjectMembershipRow.project_id == project_id)
                .order_by(InternalUserRow.name)
            )
        ).all()
        return tuple(
            ProjectMemberDetails(user_id, name, role, active)
            for user_id, name, role, active in rows
        )

    async def set_user_active(
        self,
        *,
        actor_id: UUID,
        user_id: UUID,
        active: bool,
        now: datetime,
    ) -> None:
        if not active:
            project_ids = tuple(
                (
                    await self._session.scalars(
                        select(ProjectMembershipRow.project_id)
                        .where(
                            ProjectMembershipRow.user_id == user_id,
                        )
                        .order_by(ProjectMembershipRow.project_id)
                    )
                ).all()
            )
            for project_id in project_ids:
                await self._session.scalar(
                    select(ProjectRow).where(ProjectRow.id == project_id).with_for_update()
                )
        user = await self._session.scalar(
            select(InternalUserRow).where(InternalUserRow.id == user_id).with_for_update()
        )
        if user is None:
            raise IdentityValidationError("User does not exist")
        if user.active == active:
            return
        if not active:
            current_project_ids = set(
                (
                    await self._session.scalars(
                        select(ProjectMembershipRow.project_id).where(
                            ProjectMembershipRow.user_id == user_id
                        )
                    )
                ).all()
            )
            if current_project_ids != set(project_ids):
                raise IdentityValidationError(
                    "Project membership changed concurrently; retry account deactivation"
                )
            for project_id in project_ids:
                count = await self._session.scalar(
                    select(func.count())
                    .select_from(ProjectMembershipRow)
                    .join(InternalUserRow, InternalUserRow.id == ProjectMembershipRow.user_id)
                    .where(
                        ProjectMembershipRow.project_id == project_id,
                        ProjectMembershipRow.role == "admin",
                        InternalUserRow.active.is_(True),
                    )
                )
                is_admin = await self._session.scalar(
                    select(func.count())
                    .select_from(ProjectMembershipRow)
                    .where(
                        ProjectMembershipRow.project_id == project_id,
                        ProjectMembershipRow.user_id == user_id,
                        ProjectMembershipRow.role == "admin",
                    )
                )
                if is_admin and count is not None and count <= 1:
                    raise IdentityValidationError(
                        "A project must retain at least one active administrator"
                    )
        user.active = active
        user.credential_version += 1
        if not active:
            await self._session.execute(
                update(BrowserSessionRow)
                .where(BrowserSessionRow.user_id == user_id, BrowserSessionRow.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            await self._session.execute(
                update(ProjectMembershipRow)
                .where(
                    ProjectMembershipRow.user_id == user_id, ProjectMembershipRow.role == "admin"
                )
                .values(role="developer")
            )
        await self._record_activity(
            actor_id, user_id, None, "user_enabled" if active else "user_disabled", "succeeded", now
        )

    async def issue_password_setup(
        self,
        *,
        user_id: UUID,
        digest: str,
        expires_at: datetime,
        actor_id: UUID,
        now: datetime,
    ) -> None:
        user = await self._session.get(InternalUserRow, user_id)
        if user is None or not user.active:
            raise IdentityValidationError("User does not exist or is disabled")
        await self._session.execute(
            update(PasswordSetupRow)
            .where(PasswordSetupRow.user_id == user_id, PasswordSetupRow.consumed_at.is_(None))
            .values(consumed_at=now)
        )
        self._session.add(
            PasswordSetupRow(user_id=user_id, digest=digest, expires_at=expires_at, created_at=now)
        )
        await self._record_activity(
            actor_id, user_id, None, "password_setup_issued", "succeeded", now
        )

    async def consume_password_setup(
        self, *, digest: str, password_hash: str, now: datetime
    ) -> bool:
        setup = await self._session.scalar(
            select(PasswordSetupRow).where(PasswordSetupRow.digest == digest).with_for_update()
        )
        if setup is None or setup.consumed_at is not None or setup.expires_at <= now:
            return False
        user = await self._session.scalar(
            select(InternalUserRow).where(InternalUserRow.id == setup.user_id).with_for_update()
        )
        if user is None or not user.active:
            return False
        setup.consumed_at = now
        user.password_hash = password_hash
        user.credential_version += 1
        await self._session.execute(
            update(BrowserSessionRow)
            .where(BrowserSessionRow.user_id == user.id, BrowserSessionRow.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self._record_activity(
            user.id, user.id, None, "password_setup_consumed", "succeeded", now
        )
        return True

    async def _record_activity(
        self,
        actor_id: UUID | None,
        subject_id: UUID | None,
        project_id: UUID | None,
        action: str,
        outcome: str,
        now: datetime,
    ) -> None:
        self._session.add(
            IdentityActivityRow(
                actor_id=actor_id,
                subject_id=subject_id,
                project_id=project_id,
                action=action,
                outcome=outcome,
                created_at=now,
            )
        )
