"""Pure snapshots exchanged between identity use cases and their storage port."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ProjectMembershipStatus:
    user_id: UUID
    project_id: UUID
    user_active: bool


@dataclass(frozen=True)
class ApiTokenStatus:
    token_id: UUID
    user_id: UUID
    project_id: UUID
    revoked_at: datetime | None


@dataclass(frozen=True)
class ApiTokenAuditEvent:
    actor_id: UUID | None
    project_id: UUID
    action: str
    outcome: str
    request_id: UUID


@dataclass(frozen=True)
class MembershipDetails:
    project_id: UUID
    project_name: str
    role: str


@dataclass(frozen=True)
class AccountCredentials:
    user_id: UUID
    user_name: str
    password_hash: str = field(repr=False)
    credential_version: int
    active: bool
    memberships: tuple[MembershipDetails, ...]


@dataclass(frozen=True)
class SessionPrincipal:
    user_id: UUID
    user_name: str
    session_id: UUID
    project_id: UUID | None
    project_name: str | None
    role: str | None
    scopes: tuple[str, ...]
    memberships: tuple[MembershipDetails, ...]
    csrf_token: str = field(repr=False)


@dataclass(frozen=True)
class ProjectMemberDetails:
    user_id: UUID
    user_name: str
    role: str
    active: bool
