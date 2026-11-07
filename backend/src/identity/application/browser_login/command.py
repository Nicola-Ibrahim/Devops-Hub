from dataclasses import dataclass, field

from identity.domain.browser_identity import BrowserAccount


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
