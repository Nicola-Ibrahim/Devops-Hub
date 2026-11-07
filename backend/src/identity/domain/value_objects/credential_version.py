"""Version used to fence credentials against concurrent changes."""

from dataclasses import dataclass

from identity.domain.errors import IdentityValidationError


@dataclass(frozen=True, slots=True)
class CredentialVersion:
    value: int

    def __post_init__(self) -> None:
        if self.value < 1:
            raise IdentityValidationError("Credential version must be positive")

    def next(self) -> "CredentialVersion":
        return CredentialVersion(self.value + 1)

    def matches(self, expected: int) -> bool:
        return self.value == expected
