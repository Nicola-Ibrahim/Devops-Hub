from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CreateWorkloadCommand:
    environment_id: UUID
    name: str
    template_id: str
    template_version: str


ApplicationCommand = CreateWorkloadCommand
