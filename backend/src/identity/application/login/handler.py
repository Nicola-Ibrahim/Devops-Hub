"""Application policies for internal browser login and password changes."""

import asyncio
from dataclasses import dataclass

from identity.application.login.command import (
    VerifyLoginCredentials,
)
from identity.application.shared.ports import PasswordHasher
from identity.domain.aggregates.user import User
from identity.domain.value_objects.credential_version import CredentialVersion
from identity.domain.value_objects.user_name import UserName


@dataclass(frozen=True)
class LoginCredentialsCheck:
    normalized_user_name: str
    credential_version: int | None
    accepted: bool


class VerifyLoginCredentialsHandler:
    """Normalize the submitted user and perform timing-safe credential verification."""

    def __init__(self, passwords: PasswordHasher, dummy_password_hash: str) -> None:
        self.passwords = passwords
        self.dummy_password_hash = dummy_password_hash

    @staticmethod
    def normalize_user_name(user_name: str) -> str:
        return UserName.parse(user_name).value

    async def execute(self, command: VerifyLoginCredentials) -> LoginCredentialsCheck:
        normalized = UserName.parse(command.user_name).value
        account = command.account
        encoded = account.password_hash if account is not None else self.dummy_password_hash
        matches = await asyncio.to_thread(self.passwords.verify, command.password, encoded)
        identity_account = (
            User(
                id=account.user_id,
                user_name=UserName.parse(account.user_name),
                credential_version=CredentialVersion(account.credential_version),
                active=account.active,
            )
            if account is not None
            else None
        )
        return LoginCredentialsCheck(
            normalized,
            identity_account.login_fence() if identity_account is not None else None,
            bool(
                identity_account is not None
                and identity_account.accepts_credentials(password_matches=matches)
            ),
        )
