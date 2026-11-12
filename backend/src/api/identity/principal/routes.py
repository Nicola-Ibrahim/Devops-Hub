"""Current principal route for bearer API credentials."""

from typing import Annotated

from fastapi import APIRouter, Depends

from api.core.dependencies import current_principal
from api.identity.principal.schemas import PrincipalView

router = APIRouter()


@router.get("/me", response_model=PrincipalView, tags=["identity"])
async def me(principal: Annotated[PrincipalView, Depends(current_principal)]) -> PrincipalView:
    return principal
