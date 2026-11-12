"""Private per-request credentials; never included in responses or logs."""

from dataclasses import dataclass, field
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.identity.authentication.credentials import CSRF_HEADER, browser_credentials


@dataclass(frozen=True)
class BrowserRequestCredentials:
    session_token: str = field(repr=False)
    project_id: UUID | None = None
    csrf_token: str | None = field(default=None, repr=False)
    origin: str | None = None
    mutate: bool = False


type RequestIdentity = str | BrowserRequestCredentials | None
bearer = HTTPBearer(auto_error=False)


async def request_identity(
    request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> RequestIdentity:
    browser = browser_credentials(request)
    if browser.session_token is not None:
        identity: RequestIdentity = BrowserRequestCredentials(
            browser.session_token,
            browser.project_id,
            request.headers.get(CSRF_HEADER),
            request.headers.get("origin"),
            request.method not in {"GET", "HEAD", "OPTIONS"},
        )
    else:
        identity = credentials.credentials if credentials is not None else None
    request.state.request_identity = identity
    return identity
