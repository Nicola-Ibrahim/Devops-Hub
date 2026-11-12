from dataclasses import dataclass, field

from identity.domain.records import AccountCredentials
from shared.dispatch import Command


@dataclass(frozen=True, slots=True)
class ChangePasswordCommand(Command[None]):
    session_token: str = field(repr=False)
    current_password: str = field(repr=False)
    new_password: str = field(repr=False)
    csrf_token: str = field(repr=False)
    origin: str | None


@dataclass(frozen=True, slots=True)
class VerifyPasswordChange:
    account: AccountCredentials | None = field(repr=False)
    current_password: str = field(repr=False)
    new_password: str = field(repr=False)
