"""Account invariants spanning active state and credential version."""

from dataclasses import dataclass

from identity.domain.entities.internal_user import InternalUser
from identity.domain.value_objects.credential_version import CredentialVersion


@dataclass(frozen=True, slots=True)
class IdentityAccount:
    user: InternalUser

    @classmethod
    def from_user(cls, user: InternalUser) -> "IdentityAccount":
        return cls(user)

    def accepts_credentials(self, *, password_matches: bool) -> bool:
        return self.user.active and password_matches

    def login_fence(self) -> int:
        return self.user.credential_version.value

    def next_credential_version(self) -> CredentialVersion:
        return self.user.credential_version.next()

    def may_issue_token(self) -> bool:
        return self.user.active
