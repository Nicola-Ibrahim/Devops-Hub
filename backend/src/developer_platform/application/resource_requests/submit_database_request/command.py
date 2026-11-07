from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RequestDatabaseCommand:
    project_id: UUID
    environment_id: UUID
    display_name: str
    template_id: str
    version: str
    target_id: str
    size_id: str
    ttl_seconds: int
