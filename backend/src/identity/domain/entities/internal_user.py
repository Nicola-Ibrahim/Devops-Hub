"""Internal user entity state used to make account decisions."""

from dataclasses import dataclass
from uuid import UUID

from identity.domain.value_objects.credential_version import CredentialVersion
from identity.domain.value_objects.user_name import UserName


@dataclass(frozen=True, slots=True)
class InternalUser:
    id: UUID
    user_name: UserName
    credential_version: CredentialVersion
    active: bool
