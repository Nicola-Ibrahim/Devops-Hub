from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import ApiServices, get_services
from api.errors import APIError

router = APIRouter()


@router.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready", tags=["health"])
def ready(services: Annotated[ApiServices, Depends(get_services)]) -> dict[str, str]:
    outcome = services.readiness()
    if outcome == "database_unavailable":
        raise APIError(503, "database_unavailable", "Database unavailable")
    if outcome != "ready":
        raise APIError(503, "schema_not_ready", "Run the required schema migrations")
    return {"status": "ready"}
