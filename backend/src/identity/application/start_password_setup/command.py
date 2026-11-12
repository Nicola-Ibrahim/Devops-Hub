from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StartPasswordSetupCommand:
    user_id: UUID
    actor_id: UUID
