"""Browser login, project selection and logout routes."""

from typing import Annotated

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Header, Request, Response

from api.identity.authentication.credentials import (
    CSRF_HEADER,
    SESSION_COOKIE,
    browser_credentials,
    require_cookie_session,
)
from api.identity.authentication.schemas import LoginBody, ProjectBody
from api.identity.sessions.mapping import _principal
from api.settings.config import BrowserCookiePolicy
from identity.application.login.command import LoginCommand
from identity.application.logout.command import LogoutCommand
from identity.application.logout_all_sessions.command import LogoutAllSessionsCommand
from identity.application.module import IdentityModule
from identity.application.select_active_project.command import SelectActiveProjectCommand

router = APIRouter()


@router.post("/auth/login", tags=["identity"])
@inject
async def login(
    body: LoginBody,
    request: Request,
    response: Response,
    module: FromDishka[IdentityModule],
    cookie_policy: FromDishka[BrowserCookiePolicy],
) -> dict[str, object]:
    result = await module.execute(
        LoginCommand(body.user_name, body.password, body.project_id, request.headers.get("origin"))
    )
    response.set_cookie(
        SESSION_COOKIE,
        result.session_token,
        httponly=True,
        secure=cookie_policy.secure,
        samesite="lax",
        path="/api/v1",
        max_age=8 * 60 * 60,
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "csrfToken": result.csrf_token,
        "principal": _principal(result.principal),
        "absoluteExpiresAt": result.absolute_expires_at.isoformat(),
    }


@router.post("/auth/project", tags=["identity"])
@inject
async def select_project(
    body: ProjectBody,
    request: Request,
    csrf_token: Annotated[str, Header(alias=CSRF_HEADER)],
    module: FromDishka[IdentityModule],
) -> dict[str, object]:
    principal = await module.execute(
        SelectActiveProjectCommand(
            require_cookie_session(browser_credentials(request)),
            body.project_id,
            csrf_token,
            request.headers.get("origin"),
        )
    )
    return {"csrfToken": principal.csrf_token, "principal": _principal(principal)}


@router.post("/auth/logout", status_code=204, tags=["identity"])
@inject
async def logout(
    request: Request,
    csrf_token: Annotated[str, Header(alias=CSRF_HEADER)],
    response: Response,
    module: FromDishka[IdentityModule],
    cookie_policy: FromDishka[BrowserCookiePolicy],
) -> Response:
    await module.execute(
        LogoutCommand(
            require_cookie_session(browser_credentials(request)),
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


@router.post("/auth/logout-all", tags=["identity"])
@inject
async def logout_all(
    request: Request,
    csrf_token: Annotated[str, Header(alias=CSRF_HEADER)],
    response: Response,
    module: FromDishka[IdentityModule],
    cookie_policy: FromDishka[BrowserCookiePolicy],
) -> dict[str, int]:
    count = await module.execute(
        LogoutAllSessionsCommand(
            require_cookie_session(browser_credentials(request)),
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
    return {"revoked": count}
