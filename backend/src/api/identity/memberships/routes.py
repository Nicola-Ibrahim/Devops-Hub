"""Project membership administration routes."""

from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Header, Request, Response

from api.identity.authentication.credentials import (
    CSRF_HEADER,
    browser_credentials,
    require_cookie_session,
)
from api.identity.memberships.schemas import MembershipBody
from identity.application.list_project_members.query import ListProjectMembersQuery
from identity.application.manage_project_membership.command import ManageProjectMembershipCommand
from identity.application.module import IdentityModule

router = APIRouter()


@router.get("/projects/{project_id}/members", tags=["identity"])
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


@router.put("/projects/{project_id}/members/{user_id}", status_code=204, tags=["identity"])
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


@router.delete("/projects/{project_id}/members/{user_id}", status_code=204, tags=["identity"])
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
