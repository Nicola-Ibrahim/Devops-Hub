from typing import Annotated

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends

from api.dependencies import platform_access
from api.platform.schemas import CatalogResponse
from developer_platform.application.catalog import ReadCatalog
from developer_platform.application.dto import AccessContext

router = APIRouter()


@router.get("/api/v1/catalog", response_model=CatalogResponse, tags=["catalog"])
@inject
async def catalog(
    access: Annotated[AccessContext, Depends(platform_access)],
    read_catalog: FromDishka[ReadCatalog],
) -> CatalogResponse:
    result = read_catalog.execute(access)
    return CatalogResponse(
        project_id=result.project_id, templates=list(result.templates), message=result.message
    )
