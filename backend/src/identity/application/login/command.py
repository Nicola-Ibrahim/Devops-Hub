from dataclasses import dataclass, field
from uuid import UUID

from identity.application.login.result import LoginResult
from identity.domain.records import AccountCredentials
from shared.dispatch import Command


@dataclass(frozen=True, slots=True)
class LoginCommand(Command[LoginResult]):
    user_name: str
    password: str = field(repr=False)
    project_id: UUID | None
    origin: str | None


@dataclass(frozen=True, slots=True)
class VerifyLoginCredentials:
    user_name: str
    password: str = field(repr=False)
    account: AccountCredentials | None = field(repr=False)
