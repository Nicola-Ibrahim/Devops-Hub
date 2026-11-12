from dataclasses import dataclass, field
from uuid import UUID

from shared.dispatch import Command


@dataclass(frozen=True, slots=True)
class ManageProjectMembershipCommand(Command[None]):
    session_token: str = field(repr=False)
    project_id: UUID
    user_id: UUID
    role: str | None
    csrf_token: str = field(repr=False)
    origin: str | None


@dataclass(frozen=True, slots=True)
class SetProjectMembershipCommand:
    actor_id: UUID
    user_id: UUID
    project_id: UUID
    role: str | None
