"""Project registration and metadata routes."""

from dataclasses import asdict
from typing import Annotated, Literal, cast
from uuid import UUID

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends

from api.core.dependencies import platform_access
from api.core.security.request_identity import (
    BrowserRequestCredentials,
    RequestIdentity,
    request_identity,
)
from api.platform.projects.schemas import ProjectRegistrationView
from devops_platform.application.database_provisioning.read_resources.query import (
    ReadProject,
    ReadProjects,
)
from devops_platform.application.module import DeveloperPlatformModule
from devops_platform.application.shared.dto import AccessContext
from devops_platform.authorization import ALL_SCOPES, authorize_platform_action
from identity.application.authenticate_api_token.query import AuthenticateApiTokenQuery
from identity.application.authenticate_session.query import AuthenticateSessionQuery
from identity.application.module import IdentityModule

router = APIRouter()
Access = Annotated[AccessContext, Depends(platform_access)]
Bearer = Annotated[RequestIdentity, Depends(request_identity)]


@router.get("/projects/{project_id}", response_model=ProjectRegistrationView, tags=["projects"])
@inject
async def project(
    project_id: UUID, access: Access, module: FromDishka[DeveloperPlatformModule]
) -> ProjectRegistrationView:
    message = ReadProject(access, project_id)
    authorize_platform_action(message)
    result = await module.query(message)
    return ProjectRegistrationView.model_validate(asdict(result))


@router.get("/projects", response_model=list[ProjectRegistrationView], tags=["projects"])
@inject
async def projects(
    credentials: Bearer,
    identity: FromDishka[IdentityModule],
    module: FromDishka[DeveloperPlatformModule],
) -> list[ProjectRegistrationView]:
    if isinstance(credentials, BrowserRequestCredentials):
        principal = await identity.query(AuthenticateSessionQuery(credentials.session_token))
        accesses = tuple(
            AccessContext(
                principal.user_id,
                member.project_id,
                cast(Literal["developer", "admin"], member.role),
                frozenset(ALL_SCOPES),
            )
            for member in principal.memberships
        )
    else:
        token_principal = await identity.query(AuthenticateApiTokenQuery(credentials))
        accesses = (
            AccessContext(
                token_principal.user_id,
                token_principal.project_id,
                token_principal.role,
                token_principal.scopes,
            ),
        )
    message = ReadProjects(accesses)
    authorize_platform_action(message)
    rows = await module.query(message)
    return [ProjectRegistrationView.model_validate(asdict(row)) for row in rows]
