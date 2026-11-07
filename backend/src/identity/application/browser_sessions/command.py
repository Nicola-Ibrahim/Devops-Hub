from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RefreshBrowserSessionCommand:
    session_token: str = field(repr=False)
    project_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class RotateBrowserCsrfCommand:
    session_token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ListBrowserSessionsCommand:
    session_token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class AuthorizeBrowserMutationCommand:
    session_token: str = field(repr=False)
    csrf_token: str = field(repr=False)
    origin: str | None


@dataclass(frozen=True, slots=True)
class SelectBrowserProjectCommand(AuthorizeBrowserMutationCommand):
    project_id: UUID


@dataclass(frozen=True, slots=True)
class LogoutBrowserSessionCommand(AuthorizeBrowserMutationCommand):
    pass


@dataclass(frozen=True, slots=True)
class LogoutAllBrowserSessionsCommand(AuthorizeBrowserMutationCommand):
    pass


@dataclass(frozen=True, slots=True)
class RevokeBrowserSessionCommand(AuthorizeBrowserMutationCommand):
    session_id: UUID
