"""Commands for changing browser sessions and project selection."""

from dataclasses import dataclass, field
from uuid import UUID

from identity.domain.browser_identity import BrowserPrincipal
from shared.dispatch import Command


@dataclass(frozen=True, slots=True)
class RefreshBrowserSessionCommand(Command[BrowserPrincipal]):
    session_token: str = field(repr=False)
    project_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class RotateBrowserCsrfCommand(Command[BrowserPrincipal]):
    session_token: str = field(repr=False)


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
class RevokeBrowserSessionCommand(Command[bool]):
    session_token: str = field(repr=False)
    session_id: UUID
    csrf_token: str = field(repr=False)
    origin: str | None


@dataclass(frozen=True, slots=True)
class AuthorizeBrowserMutationCommand:
    """Internal authorization input shared by protected session mutations."""

    session_token: str = field(repr=False)
    csrf_token: str = field(repr=False)
    origin: str | None
