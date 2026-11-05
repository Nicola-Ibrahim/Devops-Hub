from typing import Protocol

from identity.domain.api_tokens import ApiTokenRepository

__all__ = [
    "ApiTokenRepository",
    "CredentialDelivery",
    "CredentialReceipt",
    "PasswordHasher",
    "TokenGenerator",
    "TokenHasher",
]


class TokenHasher(Protocol):
    def digest(self, token: str) -> str: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, encoded: str) -> bool: ...


class TokenGenerator(Protocol):
    def generate(self) -> str: ...


class CredentialReceipt(Protocol):
    def remove_owned(self) -> None: ...


class CredentialDelivery(Protocol):
    def write_new(self, secret: str) -> CredentialReceipt: ...
