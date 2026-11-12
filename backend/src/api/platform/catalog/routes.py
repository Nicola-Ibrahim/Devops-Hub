"""Approved resource catalog routes."""

from dataclasses import asdict
from typing import Annotated

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends

from api.core.dependencies import platform_access
from api.platform.catalog.schemas import CatalogResponse, PostgresOptionView
from devops_platform.application.module import DeveloperPlatformModule
from devops_platform.application.resource_catalog.query import ReadCatalog
from devops_platform.application.shared.dto import AccessContext
from devops_platform.authorization import authorize_platform_action

router = APIRouter()
Access = Annotated[AccessContext, Depends(platform_access)]


@router.get("/catalog", response_model=CatalogResponse, tags=["catalog"])
@inject
async def catalog(access: Access, module: FromDishka[DeveloperPlatformModule]) -> CatalogResponse:
    message = ReadCatalog(access)
    authorize_platform_action(message)
    result = await module.query(message)
    return CatalogResponse(
        project_id=result.project_id,
        templates=[
            PostgresOptionView.model_validate(asdict(option)) for option in result.templates
        ],
        message=result.message,
    )
