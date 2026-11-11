"""Typed identity module messages for HTTP-facing identity actions."""

from dataclasses import dataclass, field
from uuid import UUID

from identity.contracts import AuthenticatedPrincipal
from identity.domain.browser_identity import (
    BrowserLogin,
    BrowserPrincipal,
    BrowserProjectMember,
    BrowserSession,
)
from shared.dispatch import Command, Query


@dataclass(frozen=True, slots=True)
class AuthenticateIdentityTokenQuery(Query[AuthenticatedPrincipal]):
    token: str | None = field(repr=False)


@dataclass(frozen=True, slots=True)
class AuthenticateBrowserSessionQuery(Query[BrowserPrincipal]):
    session_token: str = field(repr=False)
    project_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class LoginBrowserSessionCommand(Command[BrowserLogin]):
    user_name: str
    password: str = field(repr=False)
    project_id: UUID | None
    origin: str | None


@dataclass(frozen=True, slots=True)
class ReadBrowserPrincipalQuery(Query[BrowserPrincipal]):
    session_token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ReadBrowserCookiePolicyQuery(Query[bool]):
    pass


@dataclass(frozen=True, slots=True)
class SelectBrowserProjectCommand(Command[BrowserPrincipal]):
    session_token: str = field(repr=False)
    project_id: UUID
    csrf_token: str = field(repr=False)
    origin: str | None


@dataclass(frozen=True, slots=True)
class LogoutBrowserSessionCommand(Command[None]):
    session_token: str = field(repr=False)
    csrf_token: str = field(repr=False)
    origin: str | None


@dataclass(frozen=True, slots=True)
class LogoutAllBrowserSessionsCommand(Command[int]):
    session_token: str = field(repr=False)
    csrf_token: str = field(repr=False)
    origin: str | None


@dataclass(frozen=True, slots=True)
class ListBrowserSessionsQuery(Query[tuple[BrowserSession, ...]]):
    session_token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class RevokeBrowserSessionCommand(Command[bool]):
    session_token: str = field(repr=False)
    session_id: UUID
    csrf_token: str = field(repr=False)
    origin: str | None


@dataclass(frozen=True, slots=True)
class ChangeBrowserPasswordCommand(Command[None]):
    session_token: str = field(repr=False)
    current_password: str = field(repr=False)
    new_password: str = field(repr=False)
    csrf_token: str = field(repr=False)
    origin: str | None


@dataclass(frozen=True, slots=True)
class ListProjectMembersQuery(Query[tuple[BrowserProjectMember, ...]]):
    session_token: str = field(repr=False)
    project_id: UUID


@dataclass(frozen=True, slots=True)
class ManageProjectMembershipCommand(Command[None]):
    session_token: str = field(repr=False)
    project_id: UUID
    user_id: UUID
    role: str | None
    csrf_token: str = field(repr=False)
    origin: str | None
