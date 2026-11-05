"""Application policies for internal browser login and password changes."""

import asyncio
from dataclasses import dataclass

from identity.application.ports import PasswordHasher
from identity.domain.browser_credentials import normalize_user_name, validate_password
from identity.domain.browser_errors import BrowserAuthenticationRejected
from identity.domain.browser_identity import BrowserAccount


@dataclass(frozen=True)
class BrowserLoginCheck:
    normalized_user_name: str
    credential_version: int | None
    accepted: bool


@dataclass(frozen=True)
class PreparedBrowserPasswordChange:
    credential_version: int
    encoded_password: str


class CheckBrowserLogin:
    """Normalize the submitted user and perform timing-safe credential verification."""

    def __init__(self, passwords: PasswordHasher, dummy_password_hash: str) -> None:
        self.passwords = passwords
        self.dummy_password_hash = dummy_password_hash

    @staticmethod
    def normalize_user_name(user_name: str) -> str:
        return normalize_user_name(user_name)

    async def execute(
        self, user_name: str, password: str, account: BrowserAccount | None
    ) -> BrowserLoginCheck:
        normalized = normalize_user_name(user_name)
        encoded = account.password_hash if account is not None else self.dummy_password_hash
        matches = await asyncio.to_thread(self.passwords.verify, password, encoded)
        return BrowserLoginCheck(
            normalized,
            account.credential_version if account is not None else None,
            bool(account is not None and account.active and matches),
        )


class VerifyBrowserPasswordChange:
    """Validate a password change and return its encoded replacement credential."""

    def __init__(self, passwords: PasswordHasher) -> None:
        self.passwords = passwords

    async def execute(
        self, account: BrowserAccount | None, current_password: str, new_password: str
    ) -> PreparedBrowserPasswordChange:
        if account is None or not await asyncio.to_thread(
            self.passwords.verify,
            current_password,
            account.password_hash if account is not None else "",
        ):
            raise BrowserAuthenticationRejected()
        validate_password(new_password)
        return PreparedBrowserPasswordChange(
            account.credential_version,
            await asyncio.to_thread(self.passwords.hash, new_password),
        )
