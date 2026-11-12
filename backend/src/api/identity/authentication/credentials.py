"""Cookie and project-header parsing for internal browser authentication."""

from dataclasses import dataclass
from uuid import UUID

from fastapi import Request

from api.core.errors import APIError

SESSION_COOKIE = "devops_session"
PROJECT_HEADER = "X-Project-ID"
CSRF_HEADER = "X-CSRF-Token"


@dataclass(frozen=True)
class BrowserCredentials:
    session_token: str | None
    project_id: UUID | None


def browser_credentials(request: Request) -> BrowserCredentials:
    """Extract the browser session without accepting ambiguous bearer+cookie identity."""
    cookie = request.cookies.get(SESSION_COOKIE)
    authorization = request.headers.get("authorization")
    if cookie and authorization:
        raise APIError(
            400, "ambiguous_credentials", "Send either a browser session or bearer token"
        )
    raw_project = request.headers.get(PROJECT_HEADER)
    try:
        project_id = UUID(raw_project) if raw_project else None
    except ValueError:
        raise APIError(400, "invalid_project", "Project header must be a UUID") from None
    return BrowserCredentials(cookie, project_id)


def require_cookie_session(credentials: BrowserCredentials) -> str:
    if not credentials.session_token:
        raise APIError(401, "authentication_required", "Browser session is required")
    return credentials.session_token
