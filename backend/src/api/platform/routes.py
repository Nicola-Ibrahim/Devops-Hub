from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import ApiServices, get_services, platform_access
from api.platform.schemas import CatalogResponse
from developer_platform.application.dto import AccessContext

router = APIRouter()


@router.get("/api/v1/catalog", response_model=CatalogResponse, tags=["catalog"])
def catalog(
    access: Annotated[AccessContext, Depends(platform_access)],
    services: Annotated[ApiServices, Depends(get_services)],
) -> CatalogResponse:
    result = services.catalog.execute(access)
    return CatalogResponse(
        project_id=result.project_id, templates=list(result.templates), message=result.message
    )
