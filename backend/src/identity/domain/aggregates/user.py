"""User account identity and credential lifecycle rules."""

from dataclasses import dataclass, replace
from uuid import UUID

from identity.domain.value_objects.credential_version import CredentialVersion
from identity.domain.value_objects.user_name import UserName


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    user_name: UserName
    credential_version: CredentialVersion
    active: bool

    def accepts_credentials(self, *, password_matches: bool) -> bool:
        return self.active and password_matches

    def login_fence(self) -> int:
        return self.credential_version.value

    def next_credential_version(self) -> CredentialVersion:
        return self.credential_version.next()

    def may_issue_token(self) -> bool:
        return self.active

    def change_credentials(self) -> "User":
        return replace(self, credential_version=self.next_credential_version())

    def set_active(self, active: bool) -> "User":
        return replace(self, active=active, credential_version=self.next_credential_version())
