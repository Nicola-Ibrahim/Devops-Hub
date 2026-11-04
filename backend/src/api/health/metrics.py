from typing import Protocol

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Request
from fastapi.responses import Response


class OperationalMetrics(Protocol):
    async def render(self, authorization: str | None, client_host: str) -> str: ...


router = APIRouter()


@router.get("/metrics", include_in_schema=False)
@inject
async def metrics(request: Request, service: FromDishka[OperationalMetrics]) -> Response:
    value = await service.render(
        request.headers.get("authorization"), request.client.host if request.client else ""
    )
    return Response(
        value, media_type="text/plain; version=0.0.4", headers={"Cache-Control": "no-store"}
    )
