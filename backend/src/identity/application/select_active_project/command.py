from dataclasses import dataclass, field
from uuid import UUID

from identity.domain.records import SessionPrincipal
from shared.dispatch import Command


@dataclass(frozen=True, slots=True)
class SelectActiveProjectCommand(Command[SessionPrincipal]):
    session_token: str = field(repr=False)
    project_id: UUID
    csrf_token: str = field(repr=False)
    origin: str | None
