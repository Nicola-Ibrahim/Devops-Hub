from dataclasses import dataclass, field
from uuid import UUID

from shared.dispatch import Command


@dataclass(frozen=True, slots=True)
class RevokeSessionCommand(Command[bool]):
    session_token: str = field(repr=False)
    session_id: UUID
    csrf_token: str = field(repr=False)
    origin: str | None
