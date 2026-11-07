"""Identity-owned browser account, session and persistence contracts."""

from dataclasses import dataclass, field
from datetime import datetime
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
