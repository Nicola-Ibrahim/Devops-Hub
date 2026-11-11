"""HTTP translation for approved platform resources and lifecycle operations."""

from dataclasses import asdict
from typing import Annotated, Literal, cast
from uuid import UUID

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends, Header, Query, Response

from api.credentials import BrowserRequestCredentials, RequestIdentity, request_identity
from api.dependencies import platform_access
from api.platform.schemas import (
    AcceptedOperation,
    ActivityPage,
    ActivityView,
    CatalogResponse,
    ConnectionView,
    OperationView,
    PostgresOptionView,
    ProjectRegistrationView,
    RenewRequest,
    ResourcePage,
    ResourceRequest,
    ResourceView,
)
from developer_platform.application.database_lifecycle.renew_lease.command import RenewDatabaseLease
from developer_platform.application.database_provisioning.submit_database_request.command import (
    RequestDatabaseCommand,
)
from developer_platform.application.module import (
    DeleteDatabase,
    DeveloperPlatformModule,
    ReadCatalog,
    ReadDatabaseConnection,
    ReadOperation,
    ReadProject,
    ReadProjects,
    ReadResource,
    ReadResourceActivity,
    ReadResources,
    RenewDatabase,
    RequestTemporaryDatabase,
)
from developer_platform.application.shared.dto import AccessContext
from developer_platform.application.shared.permissions import ALL_SCOPES
from identity.application.module import IdentityModule
from identity.application.module_messages import (
    AuthenticateBrowserSessionQuery,
    AuthenticateIdentityTokenQuery,
)

router = APIRouter()
Access = Annotated[AccessContext, Depends(platform_access)]
Bearer = Annotated[RequestIdentity, Depends(request_identity)]


@router.get("/api/v1/catalog", response_model=CatalogResponse, tags=["catalog"])
@inject
async def catalog(access: Access, module: FromDishka[DeveloperPlatformModule]) -> CatalogResponse:
    result = await module.query(ReadCatalog(access))
    return CatalogResponse(
        project_id=result.project_id,
        templates=[
            PostgresOptionView.model_validate(asdict(option)) for option in result.templates
        ],
        message=result.message,
    )


@router.post(
    "/api/v1/resources", response_model=AcceptedOperation, status_code=202, tags=["resources"]
)
@inject
async def request_database(
    command: ResourceRequest,
    response: Response,
    access: Access,
    module: FromDishka[DeveloperPlatformModule],
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
) -> AcceptedOperation:
    result = await module.execute(
        RequestTemporaryDatabase(
            access, RequestDatabaseCommand(**command.model_dump()), idempotency_key
        )
    )
    response.headers["Location"] = f"/api/v1/operations/{result.operation_id}"
    return AcceptedOperation(**asdict(result))


@router.get(
    "/api/v1/projects/{project_id}", response_model=ProjectRegistrationView, tags=["projects"]
)
@inject
async def project(
    project_id: UUID, access: Access, module: FromDishka[DeveloperPlatformModule]
) -> ProjectRegistrationView:
    result = await module.query(ReadProject(access, project_id))
    return ProjectRegistrationView.model_validate(asdict(result))


@router.get(
    "/api/v1/projects/{project_id}/resources", response_model=ResourcePage, tags=["resources"]
)
@inject
async def resources(
    project_id: UUID,
    access: Access,
    module: FromDishka[DeveloperPlatformModule],
    after: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ResourcePage:
    results = await module.query(ReadResources(access, project_id, after, limit))
    return ResourcePage(
        items=[ResourceView.model_validate(asdict(item)) for item in results],
        next_after=results[-1].id if len(results) == limit else None,
    )


@router.get("/api/v1/resources/{resource_id}", response_model=ResourceView, tags=["resources"])
@inject
async def resource(
    resource_id: UUID, access: Access, module: FromDishka[DeveloperPlatformModule]
) -> ResourceView:
    result = await module.query(ReadResource(access, resource_id))
    return ResourceView.model_validate(asdict(result))


@router.get("/api/v1/operations/{operation_id}", response_model=OperationView, tags=["operations"])
@inject
async def operation(
    operation_id: UUID, access: Access, module: FromDishka[DeveloperPlatformModule]
) -> OperationView:
    result = await module.query(ReadOperation(access, operation_id))
    return OperationView.model_validate(asdict(result))


@router.get("/api/v1/projects", response_model=list[ProjectRegistrationView], tags=["projects"])
@inject
async def projects(
    credentials: Bearer,
    identity: FromDishka[IdentityModule],
    module: FromDishka[DeveloperPlatformModule],
) -> list[ProjectRegistrationView]:
    if isinstance(credentials, BrowserRequestCredentials):
        principal = await identity.query(AuthenticateBrowserSessionQuery(credentials.session_token))
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
        token_principal = await identity.query(AuthenticateIdentityTokenQuery(credentials))
        accesses = (
            AccessContext(
                token_principal.user_id,
                token_principal.project_id,
                token_principal.role,
                token_principal.scopes,
            ),
        )
    rows = await module.query(ReadProjects(accesses))
    return [ProjectRegistrationView.model_validate(asdict(row)) for row in rows]


@router.post(
    "/api/v1/resources/{resource_id}/renew", response_model=ResourceView, tags=["resources"]
)
@inject
async def renew(
    resource_id: UUID,
    command: RenewRequest,
    access: Access,
    module: FromDishka[DeveloperPlatformModule],
) -> ResourceView:
    row = await module.execute(
        RenewDatabase(
            access,
            RenewDatabaseLease(resource_id, command.expected_revision, command.expires_at),
        )
    )
    return ResourceView.model_validate(asdict(row))


@router.delete(
    "/api/v1/resources/{resource_id}",
    response_model=AcceptedOperation,
    status_code=202,
    tags=["resources"],
)
@inject
async def delete_resource(
    resource_id: UUID, access: Access, module: FromDishka[DeveloperPlatformModule]
) -> AcceptedOperation:
    operation_id = await module.execute(DeleteDatabase(access, resource_id))
    return AcceptedOperation(resource_id=resource_id, operation_id=operation_id)


@router.post(
    "/api/v1/resources/{resource_id}/connection", response_model=ConnectionView, tags=["resources"]
)
@inject
async def connection(
    resource_id: UUID, access: Access, module: FromDishka[DeveloperPlatformModule]
) -> ConnectionView:
    result = await module.query(ReadDatabaseConnection(access, resource_id))
    return ConnectionView.model_validate(asdict(result))


@router.get(
    "/api/v1/projects/{project_id}/activity", response_model=ActivityPage, tags=["resources"]
)
@inject
async def activity(
    project_id: UUID, access: Access, module: FromDishka[DeveloperPlatformModule]
) -> ActivityPage:
    rows = await module.query(ReadResourceActivity(access, project_id))
    return ActivityPage(items=[ActivityView.model_validate(asdict(row)) for row in rows])
