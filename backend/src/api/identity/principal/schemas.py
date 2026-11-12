from typing import Literal
from uuid import UUID

from api.core.schemas import Contract


class PrincipalView(Contract):
    user_id: UUID
    project_id: UUID
    role: Literal["developer", "admin"]
    scopes: list[str]
