from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class BootstrapFirstAdminCommand:
    user_id: UUID
    project_id: UUID
