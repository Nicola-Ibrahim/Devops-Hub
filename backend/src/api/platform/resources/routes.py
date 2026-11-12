"""Database request, inventory and lifecycle routes."""

from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends, Header, Query, Response

from api.core.dependencies import platform_access
from api.platform.resources.schemas import (
    AcceptedOperation,
    ActivityPage,
    ActivityView,
    ConnectionView,
    RenewRequest,
    ResourcePage,
    ResourceRequest,
    ResourceView,
)
from devops_platform.application.database_lifecycle.delete_database.command import (
    DeleteDatabase,
)
from devops_platform.application.database_lifecycle.read_activity.query import (
    ReadResourceActivity,
)
from devops_platform.application.database_lifecycle.read_connection.query import (
    ReadDatabaseConnection,
)
from devops_platform.application.database_lifecycle.renew_lease.command import RenewDatabase
from devops_platform.application.database_provisioning.read_resources.query import (
    ReadResource,
    ReadResources,
)
from devops_platform.application.database_provisioning.submit_database_request.command import (
    DatabaseRequest,
    RequestTemporaryDatabase,
)
from devops_platform.application.module import DeveloperPlatformModule
from devops_platform.application.shared.dto import AccessContext
from devops_platform.authorization import authorize_platform_action

router = APIRouter()
Access = Annotated[AccessContext, Depends(platform_access)]


@router.post("/resources", response_model=AcceptedOperation, status_code=202, tags=["resources"])
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
    message = RequestTemporaryDatabase(
        access, DatabaseRequest(**command.model_dump()), idempotency_key
    )
    authorize_platform_action(message)
    result = await module.execute(message)
    response.headers["Location"] = f"/api/v1/operations/{result.operation_id}"
    return AcceptedOperation(**asdict(result))


@router.get("/projects/{project_id}/resources", response_model=ResourcePage, tags=["resources"])
@inject
async def resources(
    project_id: UUID,
    access: Access,
    module: FromDishka[DeveloperPlatformModule],
    after: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ResourcePage:
    message = ReadResources(access, project_id, after, limit)
    authorize_platform_action(message)
    results = await module.query(message)
    return ResourcePage(
        items=[ResourceView.model_validate(asdict(item)) for item in results],
        next_after=results[-1].id if len(results) == limit else None,
    )


@router.get("/resources/{resource_id}", response_model=ResourceView, tags=["resources"])
@inject
async def resource(
    resource_id: UUID, access: Access, module: FromDishka[DeveloperPlatformModule]
) -> ResourceView:
    message = ReadResource(access, resource_id)
    authorize_platform_action(message)
    result = await module.query(message)
    return ResourceView.model_validate(asdict(result))


@router.post("/resources/{resource_id}/renew", response_model=ResourceView, tags=["resources"])
@inject
async def renew(
    resource_id: UUID,
    command: RenewRequest,
    access: Access,
    module: FromDishka[DeveloperPlatformModule],
) -> ResourceView:
    message = RenewDatabase(access, resource_id, command.expected_revision, command.expires_at)
    authorize_platform_action(message)
    row = await module.execute(message)
    return ResourceView.model_validate(asdict(row))


@router.delete(
    "/resources/{resource_id}",
    response_model=AcceptedOperation,
    status_code=202,
    tags=["resources"],
)
@inject
async def delete_resource(
    resource_id: UUID, access: Access, module: FromDishka[DeveloperPlatformModule]
) -> AcceptedOperation:
    message = DeleteDatabase(access, resource_id)
    authorize_platform_action(message)
    operation_id = await module.execute(message)
    return AcceptedOperation(resource_id=resource_id, operation_id=operation_id)


@router.post(
    "/resources/{resource_id}/connection", response_model=ConnectionView, tags=["resources"]
)
@inject
async def connection(
    resource_id: UUID, access: Access, module: FromDishka[DeveloperPlatformModule]
) -> ConnectionView:
    message = ReadDatabaseConnection(access, resource_id)
    authorize_platform_action(message)
    result = await module.query(message)
    return ConnectionView.model_validate(asdict(result))


@router.get("/projects/{project_id}/activity", response_model=ActivityPage, tags=["resources"])
@inject
async def activity(
    project_id: UUID, access: Access, module: FromDishka[DeveloperPlatformModule]
) -> ActivityPage:
    message = ReadResourceActivity(access, project_id)
    authorize_platform_action(message)
    rows = await module.query(message)
    return ActivityPage(items=[ActivityView.model_validate(asdict(row)) for row in rows])
