"""Application policies for internal browser login and password changes."""

import asyncio
from dataclasses import dataclass

from identity.application.browser_login.command import (
    CheckBrowserLoginCommand,
    VerifyBrowserPasswordChangeCommand,
)
from identity.application.shared.ports import PasswordHasher
from identity.domain.aggregates.identity_account import IdentityAccount
from identity.domain.browser_credentials import validate_password
from identity.domain.browser_errors import BrowserAuthenticationRejected
from identity.domain.entities.internal_user import InternalUser
from identity.domain.value_objects.credential_version import CredentialVersion
from identity.domain.value_objects.user_name import UserName


@dataclass(frozen=True)
class BrowserLoginCheck:
    normalized_user_name: str
    credential_version: int | None
    accepted: bool


@dataclass(frozen=True)
class PreparedBrowserPasswordChange:
    credential_version: int
    encoded_password: str


class CheckBrowserLoginHandler:
    """Normalize the submitted user and perform timing-safe credential verification."""

    def __init__(self, passwords: PasswordHasher, dummy_password_hash: str) -> None:
        self.passwords = passwords
        self.dummy_password_hash = dummy_password_hash

    @staticmethod
    def normalize_user_name(user_name: str) -> str:
        return UserName.parse(user_name).value

    async def execute(self, command: CheckBrowserLoginCommand) -> BrowserLoginCheck:
        normalized = UserName.parse(command.user_name).value
        account = command.account
        encoded = account.password_hash if account is not None else self.dummy_password_hash
        matches = await asyncio.to_thread(self.passwords.verify, command.password, encoded)
        identity_account = (
            IdentityAccount.from_user(
                InternalUser(
                    id=account.user_id,
                    user_name=UserName.parse(account.user_name),
                    credential_version=CredentialVersion(account.credential_version),
                    active=account.active,
                )
            )
            if account is not None
            else None
        )
        return BrowserLoginCheck(
            normalized,
            identity_account.login_fence() if identity_account is not None else None,
            bool(
                identity_account is not None
                and identity_account.accepts_credentials(password_matches=matches)
            ),
        )


class VerifyBrowserPasswordChangeHandler:
    """Validate a password change and return its encoded replacement credential."""

    def __init__(self, passwords: PasswordHasher) -> None:
        self.passwords = passwords

    async def execute(
        self, command: VerifyBrowserPasswordChangeCommand
    ) -> PreparedBrowserPasswordChange:
        account = command.account
        if account is None or not await asyncio.to_thread(
            self.passwords.verify,
            command.current_password,
            account.password_hash if account is not None else "",
        ):
            raise BrowserAuthenticationRejected()
        validate_password(command.new_password)
        return PreparedBrowserPasswordChange(
            account.credential_version,
            await asyncio.to_thread(self.passwords.hash, command.new_password),
        )
