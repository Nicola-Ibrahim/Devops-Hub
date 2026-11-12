from dataclasses import dataclass, field

from shared.dispatch import Command


@dataclass(frozen=True, slots=True)
class LogoutAllSessionsCommand(Command[int]):
    session_token: str = field(repr=False)
    csrf_token: str = field(repr=False)
    origin: str | None
