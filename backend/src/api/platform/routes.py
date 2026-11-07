from dataclasses import asdict
from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends, Header, Query, Response

from api.credentials import RequestIdentity, request_identity
from api.dependencies import platform_access
from api.platform.capabilities import PlatformRequestQueries
from api.platform.schemas import (
    AcceptedOperation,
    ActivityPage,
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
from developer_platform.application.resource_catalog.handler import ReadCatalogQueryHandler
from developer_platform.application.shared.dto import AccessContext

router = APIRouter()


@router.get("/api/v1/catalog", response_model=CatalogResponse, tags=["catalog"])
@inject
async def catalog(
    access: Annotated[AccessContext, Depends(platform_access)],
    read_catalog: FromDishka[ReadCatalogQueryHandler],
) -> CatalogResponse:
    result = read_catalog.execute(access)
    return CatalogResponse(
        project_id=result.project_id,
        templates=[
            PostgresOptionView.model_validate(asdict(option)) for option in result.templates
        ],
        message=result.message,
    )


Bearer = Annotated[RequestIdentity, Depends(request_identity)]


def credential(value: RequestIdentity) -> RequestIdentity:
    return value


@router.post(
    "/api/v1/resources", response_model=AcceptedOperation, status_code=202, tags=["resources"]
)
@inject
async def request_database(
    command: ResourceRequest,
    response: Response,
    credentials: Bearer,
    queries: FromDishka[PlatformRequestQueries],
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
) -> AcceptedOperation:
    result = await queries.request_database(credential(credentials), command, idempotency_key)
    response.headers["Location"] = f"/api/v1/operations/{result.operation_id}"
    return result


@router.get(
    "/api/v1/projects/{project_id}", response_model=ProjectRegistrationView, tags=["projects"]
)
@inject
async def project(
    project_id: UUID, credentials: Bearer, queries: FromDishka[PlatformRequestQueries]
) -> ProjectRegistrationView:
    return await queries.project(credential(credentials), project_id)


@router.get(
    "/api/v1/projects/{project_id}/resources", response_model=ResourcePage, tags=["resources"]
)
@inject
async def resources(
    project_id: UUID,
    credentials: Bearer,
    queries: FromDishka[PlatformRequestQueries],
    after: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ResourcePage:
    return await queries.resources(credential(credentials), project_id, after, limit)


@router.get("/api/v1/resources/{resource_id}", response_model=ResourceView, tags=["resources"])
@inject
async def resource(
    resource_id: UUID, credentials: Bearer, queries: FromDishka[PlatformRequestQueries]
) -> ResourceView:
    return await queries.resource(credential(credentials), resource_id)


@router.get("/api/v1/operations/{operation_id}", response_model=OperationView, tags=["operations"])
@inject
async def operation(
    operation_id: UUID, credentials: Bearer, queries: FromDishka[PlatformRequestQueries]
) -> OperationView:
    return await queries.operation(credential(credentials), operation_id)


@router.get("/api/v1/projects", response_model=list[ProjectRegistrationView], tags=["projects"])
@inject
async def projects(
    credentials: Bearer, queries: FromDishka[PlatformRequestQueries]
) -> list[ProjectRegistrationView]:
    return await queries.projects(credential(credentials))


@router.post(
    "/api/v1/resources/{resource_id}/renew", response_model=ResourceView, tags=["resources"]
)
@inject
async def renew(
    resource_id: UUID,
    command: RenewRequest,
    credentials: Bearer,
    queries: FromDishka[PlatformRequestQueries],
) -> ResourceView:
    return await queries.renew(credential(credentials), resource_id, command)


@router.delete(
    "/api/v1/resources/{resource_id}",
    response_model=AcceptedOperation,
    status_code=202,
    tags=["resources"],
)
@inject
async def delete_resource(
    resource_id: UUID, credentials: Bearer, queries: FromDishka[PlatformRequestQueries]
) -> AcceptedOperation:
    return await queries.delete(credential(credentials), resource_id)


@router.post(
    "/api/v1/resources/{resource_id}/connection", response_model=ConnectionView, tags=["resources"]
)
@inject
async def connection(
    resource_id: UUID, credentials: Bearer, queries: FromDishka[PlatformRequestQueries]
) -> ConnectionView:
    return await queries.connection(credential(credentials), resource_id)


@router.get(
    "/api/v1/projects/{project_id}/activity", response_model=ActivityPage, tags=["resources"]
)
@inject
async def activity(
    project_id: UUID, credentials: Bearer, queries: FromDishka[PlatformRequestQueries]
) -> ActivityPage:
    return await queries.activity(credential(credentials), project_id)
