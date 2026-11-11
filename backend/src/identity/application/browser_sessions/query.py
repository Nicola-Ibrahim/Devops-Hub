"""Read-only browser-session queries."""

from dataclasses import dataclass, field
from uuid import UUID

from identity.domain.browser_identity import BrowserPrincipal, BrowserSession
from shared.dispatch import Query


@dataclass(frozen=True, slots=True)
class AuthenticateBrowserSessionQuery(Query[BrowserPrincipal]):
    session_token: str = field(repr=False)
    project_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ListBrowserSessionsQuery(Query[tuple[BrowserSession, ...]]):
    session_token: str = field(repr=False)
