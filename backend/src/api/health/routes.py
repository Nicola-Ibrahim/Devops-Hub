from uuid import UUID

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter

from api.errors import APIError
from identity.application.authorization.models import AuthorizationRequest
from identity.application.authorization.port import (
    AuthorizationDecisionPort,
    AuthorizationUnavailable,
)
from shared.infra.readiness import ReadinessProbe

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


@router.get("/health/authorization", tags=["health"])
@inject
async def authorization_ready(authorizer: FromDishka[AuthorizationDecisionPort]) -> dict[str, str]:
    try:
        decision = await authorizer.evaluate(
            AuthorizationRequest(UUID(int=0), "health.probe", "health")
        )
    except AuthorizationUnavailable:
        raise APIError(503, "authorization_unavailable", "Authorization unavailable") from None
    if decision.allowed or decision.policy_revision != "identity-v1":
        raise APIError(503, "authorization_not_ready", "Authorization policy not ready")
    return {"status": "ready"}
