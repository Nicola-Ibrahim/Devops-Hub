from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ApplicationCommand:
    environment_id: UUID
    name: str
    template_id: str
    template_version: str
