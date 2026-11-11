from dataclasses import dataclass, field
from uuid import UUID

from identity.domain.browser_identity import BrowserAccount, BrowserLogin
from shared.dispatch import Command


@dataclass(frozen=True, slots=True)
class LoginBrowserSessionCommand(Command[BrowserLogin]):
    user_name: str
    password: str = field(repr=False)
    project_id: UUID | None
    origin: str | None


@dataclass(frozen=True, slots=True)
class ChangeBrowserPasswordCommand(Command[None]):
    session_token: str = field(repr=False)
    current_password: str = field(repr=False)
    new_password: str = field(repr=False)
    csrf_token: str = field(repr=False)
    origin: str | None


@dataclass(frozen=True, slots=True)
class CheckBrowserLoginCommand:
    user_name: str
    password: str = field(repr=False)
    account: BrowserAccount | None = field(repr=False)


@dataclass(frozen=True, slots=True)
class VerifyBrowserPasswordChangeCommand:
    account: BrowserAccount | None = field(repr=False)
    current_password: str = field(repr=False)
    new_password: str = field(repr=False)
