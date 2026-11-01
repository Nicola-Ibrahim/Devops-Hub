from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import current_principal
from api.identity.schemas import PrincipalView

router = APIRouter()


@router.get("/api/v1/me", response_model=PrincipalView, tags=["identity"])
async def me(
    principal: Annotated[PrincipalView, Depends(current_principal)],
) -> PrincipalView:
    return principal
