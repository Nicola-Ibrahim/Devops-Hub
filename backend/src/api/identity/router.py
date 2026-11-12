"""Identity HTTP router assembled from feature routers."""

from uuid import UUID

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends, Request

from api.core.errors import APIError
from api.identity.authentication.credentials import browser_credentials, require_cookie_session
from api.identity.authentication.routes import router as authentication_router
from api.identity.authentication.schemas import ProjectBody
from api.identity.authorization import require_identity_permission
from api.identity.memberships.routes import router as memberships_router
from api.identity.principal.routes import router as principal_router
from api.identity.sessions.routes import router as sessions_router
from identity.application.authorization.port import AuthorizationDecisionPort
from identity.application.module import IdentityModule

_IDENTITY_ACTIONS = {
    "browser_me": "identity.sessions.read",
    "select_project": "identity.project.select",
    "logout": "identity.logout",
    "logout_all": "identity.logout_all",
    "sessions": "identity.sessions.read",
    "revoke_session": "identity.sessions.revoke",
    "change_password": "identity.password.change",
    "list_project_members": "identity.members.read",
    "set_project_member": "identity.members.write",
    "remove_project_member": "identity.members.write",
}


@inject
async def identity_route_permission(
    request: Request,
    module: FromDishka[IdentityModule],
    authorizer: FromDishka[AuthorizationDecisionPort],
) -> None:
    route_name = request.scope["route"].name
    if route_name == "login":
        return
    action = _IDENTITY_ACTIONS.get(route_name)
    if action is None:
        raise APIError(403, "forbidden", "Permission denied")
    try:
        project_id = (
            UUID(str(request.path_params["project_id"]))
            if "project_id" in request.path_params
            else None
        )
        session_id = (
            UUID(str(request.path_params["session_id"]))
            if "session_id" in request.path_params
            else None
        )
    except ValueError:
        raise APIError(422, "invalid_request", "Request validation failed") from None
    if route_name == "select_project":
        try:
            project_id = ProjectBody.model_validate(await request.json()).project_id
        except ValueError:
            raise APIError(422, "invalid_request", "Request validation failed") from None
    await require_identity_permission(
        module=module,
        authorizer=authorizer,
        session_token=require_cookie_session(browser_credentials(request)),
        action=action,
        resource_kind="project_membership"
        if "members" in route_name or "member" in route_name
        else "session",
        resource_id=session_id,
        project_id=project_id,
    )


router = APIRouter(prefix="/api/v1")
for feature_router in (
    authentication_router,
    sessions_router,
    memberships_router,
):
    router.include_router(feature_router, dependencies=[Depends(identity_route_permission)])
router.include_router(principal_router)
