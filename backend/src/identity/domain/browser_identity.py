"""Identity-owned browser account, session and persistence contracts."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class BrowserMembership:
    project_id: UUID
    project_name: str
    role: str


@dataclass(frozen=True)
class BrowserAccount:
    user_id: UUID
    user_name: str
    password_hash: str = field(repr=False)
    credential_version: int
    active: bool
    memberships: tuple[BrowserMembership, ...]


@dataclass(frozen=True)
class BrowserPrincipal:
    user_id: UUID
    user_name: str
    session_id: UUID
    project_id: UUID | None
    project_name: str | None
    role: str | None
    scopes: tuple[str, ...]
    memberships: tuple[BrowserMembership, ...]
    csrf_token: str = field(repr=False)


@dataclass(frozen=True)
class BrowserLogin:
    session_token: str = field(repr=False)
    csrf_token: str = field(repr=False)
    principal: BrowserPrincipal
    absolute_expires_at: datetime


@dataclass(frozen=True)
class BrowserSession:
    session_id: UUID
    created_at: datetime
    last_seen_at: datetime
    idle_expires_at: datetime
    absolute_expires_at: datetime
    current: bool


@dataclass(frozen=True)
class BrowserProjectMember:
    user_id: UUID
    user_name: str
    role: str
    active: bool


class BrowserIdentityRepository(Protocol):
    """Identity persistence port; transaction completion belongs to the host."""

    async def find_login_account(self, user_name: str) -> BrowserAccount | None: ...

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
    ) -> tuple[BrowserPrincipal, UUID, datetime] | None: ...

    async def authenticate_session(
        self, *, token_digest: str, project_id: UUID | None, now: datetime
    ) -> tuple[BrowserPrincipal, str] | None: ...

    async def authorize_browser_operation(
        self,
        token_digest: str,
        project_id: UUID | None,
        now: datetime,
        *,
        lock_for_mutation: bool = False,
    ) -> BrowserPrincipal | None: ...

    async def rotate_csrf(self, token_digest: str, csrf_digest: str, now: datetime) -> bool: ...

    async def select_project(
        self, *, token_digest: str, project_id: UUID, now: datetime
    ) -> BrowserPrincipal | None: ...

    async def logout(self, token_digest: str, now: datetime) -> None: ...

    async def logout_all(self, user_id: UUID, now: datetime) -> int: ...

    async def list_sessions(
        self, user_id: UUID, current_session_id: UUID, now: datetime
    ) -> tuple[BrowserSession, ...]: ...

    async def revoke_session(self, user_id: UUID, session_id: UUID, now: datetime) -> bool: ...

    async def change_password(
        self, *, user_id: UUID, expected_version: int, password_hash: str, now: datetime
    ) -> bool: ...

    async def validate_csrf(self, token_digest: str, csrf_digest: str) -> bool: ...

    async def create_user(
        self, user_name: str, password_hash: str, actor_id: UUID | None, now: datetime
    ) -> UUID: ...

    async def set_membership(
        self,
        *,
        actor_id: UUID,
        user_id: UUID,
        project_id: UUID,
        role: str | None,
        now: datetime,
    ) -> None: ...

    async def bootstrap_first_project_admin(
        self, *, user_id: UUID, project_id: UUID, now: datetime
    ) -> None: ...

    async def list_project_members(
        self, *, actor_id: UUID, project_id: UUID
    ) -> tuple[BrowserProjectMember, ...]: ...

    async def set_user_active(
        self, *, actor_id: UUID, user_id: UUID, active: bool, now: datetime
    ) -> None: ...

    async def lock_project_membership_admin_scope(self, project_id: UUID) -> bool: ...

    async def issue_password_setup(
        self,
        *,
        user_id: UUID,
        digest: str,
        expires_at: datetime,
        actor_id: UUID,
        now: datetime,
    ) -> None: ...

    async def consume_password_setup(
        self, *, digest: str, password_hash: str, now: datetime
    ) -> bool: ...
