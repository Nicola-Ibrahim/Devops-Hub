"""Current-session, session-list and password routes."""

from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Header, Request, Response

from api.identity.authentication.credentials import (
    CSRF_HEADER,
    SESSION_COOKIE,
    browser_credentials,
    require_cookie_session,
)
from api.identity.sessions.mapping import _principal
from api.identity.sessions.schemas import PasswordBody
from api.settings.config import BrowserCookiePolicy
from identity.application.change_password.command import ChangePasswordCommand
from identity.application.list_sessions.query import ListSessionsQuery
from identity.application.module import IdentityModule
from identity.application.revoke_session.command import RevokeSessionCommand
from identity.application.rotate_csrf.command import RotateCsrfCommand

router = APIRouter()


@router.get("/me/browser", tags=["identity"])
@inject
async def browser_me(
    request: Request, response: Response, module: FromDishka[IdentityModule]
) -> dict[str, object]:
    principal = await module.execute(
        RotateCsrfCommand(require_cookie_session(browser_credentials(request)))
    )
    response.headers["Cache-Control"] = "no-store"
    return {"csrfToken": principal.csrf_token, "principal": _principal(principal)}


@router.get("/me/sessions", tags=["identity"])
@inject
async def sessions(
    request: Request,
    response: Response,
    module: FromDishka[IdentityModule],
) -> list[dict[str, object]]:
    response.headers["Cache-Control"] = "no-store"
    values = await module.query(
        ListSessionsQuery(require_cookie_session(browser_credentials(request)))
    )
    return [
        {
            "sessionId": str(item.session_id),
            "createdAt": item.created_at.isoformat(),
            "lastSeenAt": item.last_seen_at.isoformat(),
            "idleExpiresAt": item.idle_expires_at.isoformat(),
            "absoluteExpiresAt": item.absolute_expires_at.isoformat(),
            "current": item.current,
        }
        for item in values
    ]


@router.delete("/me/sessions/{session_id}", status_code=204, tags=["identity"])
@inject
async def revoke_session(
    session_id: UUID,
    request: Request,
    csrf_token: Annotated[str, Header(alias=CSRF_HEADER)],
    response: Response,
    module: FromDishka[IdentityModule],
) -> Response:
    await module.execute(
        RevokeSessionCommand(
            require_cookie_session(browser_credentials(request)),
            session_id,
            csrf_token,
            request.headers.get("origin"),
        )
    )
    response.status_code = 204
    return response


@router.post("/me/password", status_code=204, tags=["identity"])
@inject
async def change_password(
    body: PasswordBody,
    request: Request,
    csrf_token: Annotated[str, Header(alias=CSRF_HEADER)],
    response: Response,
    module: FromDishka[IdentityModule],
    cookie_policy: FromDishka[BrowserCookiePolicy],
) -> Response:
    await module.execute(
        ChangePasswordCommand(
            require_cookie_session(browser_credentials(request)),
            body.current_password,
            body.new_password,
            csrf_token,
            request.headers.get("origin"),
        )
    )
    response.delete_cookie(
        SESSION_COOKIE,
        path="/api/v1",
        secure=cookie_policy.secure,
        httponly=True,
        samesite="lax",
    )
    response.status_code = 204
    return response
