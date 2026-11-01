from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter

from api.dependencies import ReadinessProbe
from api.errors import APIError

router = APIRouter()


@router.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready", tags=["health"])
@inject
async def ready(probe: FromDishka[ReadinessProbe]) -> dict[str, str]:
    outcome = await probe.inspect()
    if outcome == "database_unavailable":
        raise APIError(503, "database_unavailable", "Database unavailable")
    if outcome != "ready":
        raise APIError(503, "schema_not_ready", "Run the required schema migrations")
    return {"status": "ready"}
