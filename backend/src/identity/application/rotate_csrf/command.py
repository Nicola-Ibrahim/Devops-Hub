from dataclasses import dataclass, field

from identity.domain.records import SessionPrincipal
from shared.dispatch import Command


@dataclass(frozen=True, slots=True)
class RotateCsrfCommand(Command[SessionPrincipal]):
    session_token: str = field(repr=False)
