"""Cookie-based internal identity HTTP contract and transport routes."""

from dataclasses import dataclass
from typing import Annotated, Literal
from uuid import UUID

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from api.errors import APIError
from api.identity.cookie_policy import BrowserCookiePolicy
from identity.application.browser_login.command import (
    ChangeBrowserPasswordCommand,
    LoginBrowserSessionCommand,
)
from identity.application.browser_sessions.command import (
    LogoutAllBrowserSessionsCommand,
    LogoutBrowserSessionCommand,
    RevokeBrowserSessionCommand,
    RotateBrowserCsrfCommand,
    SelectBrowserProjectCommand,
)
from identity.application.browser_sessions.query import (
    ListBrowserSessionsQuery,
)
from identity.application.module import IdentityModule
from identity.application.project_memberships.command import ManageProjectMembershipCommand
from identity.application.project_memberships.query import (
    ListProjectMembersQuery,
)
from identity.domain.browser_identity import (
    BrowserPrincipal,
)

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


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_name: str = Field(alias="userName", min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=1024, repr=False)
    project_id: UUID | None = Field(default=None, alias="projectId")


class ProjectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID = Field(alias="projectId")


class PasswordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(
        alias="currentPassword", min_length=1, max_length=1024, repr=False
    )
    new_password: str = Field(alias="newPassword", min_length=12, max_length=1024, repr=False)


class MembershipBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["developer", "admin"]


def _principal(principal: BrowserPrincipal) -> dict[str, object]:
    return {
        "userId": str(principal.user_id),
        "userName": principal.user_name,
        "sessionId": str(principal.session_id),
        "projectId": str(principal.project_id) if principal.project_id else None,
        "projectName": principal.project_name,
        "role": principal.role,
        "scopes": list(principal.scopes),
        "csrfToken": principal.csrf_token,
        "memberships": [
            {
                "projectId": str(member.project_id),
                "projectName": member.project_name,
                "role": member.role,
            }
            for member in principal.memberships
        ],
    }


router = APIRouter()


@router.post("/api/v1/auth/login", tags=["identity"])
@inject
async def login(
    body: LoginBody,
    request: Request,
    response: Response,
    module: FromDishka[IdentityModule],
    cookie_policy: FromDishka[BrowserCookiePolicy],
) -> dict[str, object]:
    result = await module.execute(
        LoginBrowserSessionCommand(
            body.user_name, body.password, body.project_id, request.headers.get("origin")
        )
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


@router.get("/api/v1/me/browser", tags=["identity"])
@inject
async def browser_me(
    request: Request, response: Response, module: FromDishka[IdentityModule]
) -> dict[str, object]:
    principal = await module.execute(
        RotateBrowserCsrfCommand(require_cookie_session(browser_credentials(request)))
    )
    response.headers["Cache-Control"] = "no-store"
    return {"csrfToken": principal.csrf_token, "principal": _principal(principal)}


@router.post("/api/v1/auth/project", tags=["identity"])
@inject
async def select_project(
    body: ProjectBody,
    request: Request,
    csrf_token: Annotated[str, Header(alias=CSRF_HEADER)],
    module: FromDishka[IdentityModule],
) -> dict[str, object]:
    principal = await module.execute(
        SelectBrowserProjectCommand(
            require_cookie_session(browser_credentials(request)),
            body.project_id,
            csrf_token,
            request.headers.get("origin"),
        )
    )
    return {"csrfToken": principal.csrf_token, "principal": _principal(principal)}


@router.post("/api/v1/auth/logout", status_code=204, tags=["identity"])
@inject
async def logout(
    request: Request,
    csrf_token: Annotated[str, Header(alias=CSRF_HEADER)],
    response: Response,
    module: FromDishka[IdentityModule],
    cookie_policy: FromDishka[BrowserCookiePolicy],
) -> Response:
    await module.execute(
        LogoutBrowserSessionCommand(
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


@router.post("/api/v1/auth/logout-all", tags=["identity"])
@inject
async def logout_all(
    request: Request,
    csrf_token: Annotated[str, Header(alias=CSRF_HEADER)],
    response: Response,
    module: FromDishka[IdentityModule],
    cookie_policy: FromDishka[BrowserCookiePolicy],
) -> dict[str, int]:
    count = await module.execute(
        LogoutAllBrowserSessionsCommand(
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


@router.get("/api/v1/me/sessions", tags=["identity"])
@inject
async def sessions(
    request: Request,
    response: Response,
    module: FromDishka[IdentityModule],
) -> list[dict[str, object]]:
    response.headers["Cache-Control"] = "no-store"
    values = await module.query(
        ListBrowserSessionsQuery(require_cookie_session(browser_credentials(request)))
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


@router.delete("/api/v1/me/sessions/{session_id}", status_code=204, tags=["identity"])
@inject
async def revoke_session(
    session_id: UUID,
    request: Request,
    csrf_token: Annotated[str, Header(alias=CSRF_HEADER)],
    response: Response,
    module: FromDishka[IdentityModule],
) -> Response:
    await module.execute(
        RevokeBrowserSessionCommand(
            require_cookie_session(browser_credentials(request)),
            session_id,
            csrf_token,
            request.headers.get("origin"),
        )
    )
    response.status_code = 204
    return response


@router.post("/api/v1/me/password", status_code=204, tags=["identity"])
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
        ChangeBrowserPasswordCommand(
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


@router.get("/api/v1/projects/{project_id}/members", tags=["identity"])
@inject
async def list_project_members(
    project_id: UUID,
    request: Request,
    response: Response,
    module: FromDishka[IdentityModule],
) -> list[dict[str, object]]:
    response.headers["Cache-Control"] = "no-store"
    members = await module.query(
        ListProjectMembersQuery(require_cookie_session(browser_credentials(request)), project_id)
    )
    return [
        {
            "userId": str(member.user_id),
            "userName": member.user_name,
            "role": member.role,
            "active": member.active,
        }
        for member in members
    ]


@router.put("/api/v1/projects/{project_id}/members/{user_id}", status_code=204, tags=["identity"])
@inject
async def set_project_member(
    project_id: UUID,
    user_id: UUID,
    body: MembershipBody,
    request: Request,
    csrf_token: Annotated[str, Header(alias=CSRF_HEADER)],
    response: Response,
    module: FromDishka[IdentityModule],
) -> Response:
    await module.execute(
        ManageProjectMembershipCommand(
            require_cookie_session(browser_credentials(request)),
            project_id,
            user_id,
            body.role,
            csrf_token,
            request.headers.get("origin"),
        )
    )
    response.status_code = 204
    return response


@router.delete(
    "/api/v1/projects/{project_id}/members/{user_id}", status_code=204, tags=["identity"]
)
@inject
async def remove_project_member(
    project_id: UUID,
    user_id: UUID,
    request: Request,
    csrf_token: Annotated[str, Header(alias=CSRF_HEADER)],
    response: Response,
    module: FromDishka[IdentityModule],
) -> Response:
    await module.execute(
        ManageProjectMembershipCommand(
            require_cookie_session(browser_credentials(request)),
            project_id,
            user_id,
            None,
            csrf_token,
            request.headers.get("origin"),
        )
    )
    response.status_code = 204
    return response
