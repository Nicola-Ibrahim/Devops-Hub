from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SetUserStatusCommand:
    actor_id: UUID
    user_id: UUID
    active: bool
