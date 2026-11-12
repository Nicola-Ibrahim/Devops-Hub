from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreateUserCommand:
    user_name: str
    password: str = field(repr=False)
    actor_id: UUID | None = None
