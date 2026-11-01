from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import current_principal
from api.identity.schemas import PrincipalView
from identity.contracts import AuthenticatedPrincipal

router = APIRouter()


@router.get("/api/v1/me", response_model=PrincipalView, tags=["identity"])
def me(principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)]) -> PrincipalView:
    return PrincipalView(
        user_id=principal.user_id,
        project_id=principal.project_id,
        role=principal.role,
        scopes=sorted(principal.scopes),
    )
