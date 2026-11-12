"""Password change validation and hashing policy."""

import asyncio
from dataclasses import dataclass

from identity.application.change_password.command import VerifyPasswordChange
from identity.application.shared.ports import PasswordHasher
from identity.domain.browser_credentials import validate_password
from identity.domain.browser_errors import BrowserAuthenticationRejected


@dataclass(frozen=True)
class PreparedPasswordChange:
    credential_version: int
    encoded_password: str


class VerifyPasswordChangeHandler:
    def __init__(self, passwords: PasswordHasher) -> None:
        self.passwords = passwords

    async def execute(self, command: VerifyPasswordChange) -> PreparedPasswordChange:
        account = command.account
        if account is None or not await asyncio.to_thread(
            self.passwords.verify,
            command.current_password,
            account.password_hash if account is not None else "",
        ):
            raise BrowserAuthenticationRejected()
        validate_password(command.new_password)
        return PreparedPasswordChange(
            account.credential_version,
            await asyncio.to_thread(self.passwords.hash, command.new_password),
        )
