from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

from identity.domain.credentials import CredentialSnapshot
from identity.domain.records import AuditRecord, IdentitySnapshot, TokenSnapshot


class TokenHasher(Protocol):
    def digest(self, token: str) -> str: ...


class TokenGenerator(Protocol):
    def generate(self) -> str: ...


class AuthenticationReader(Protocol):
    def find_by_digest(self, digest: str) -> CredentialSnapshot | None: ...


class CredentialReceipt(Protocol):
    def remove_owned(self) -> None: ...


class CredentialDelivery(Protocol):
    def write_new(self, secret: str) -> CredentialReceipt: ...


class IdentityTransaction(Protocol):
    def __enter__(self) -> "IdentityTransaction": ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    def ensure_identity(
        self,
        *,
        user_name: str,
        project_name: str,
        new_role: str,
    ) -> IdentitySnapshot: ...

    def add_token(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        digest: str,
        scopes: tuple[str, ...],
        expires_at: datetime,
        created_at: datetime,
    ) -> UUID: ...

    def append_audit(self, event: AuditRecord) -> None: ...

    def find_token(self, token_id: UUID) -> TokenSnapshot | None: ...

    def set_revoked(self, token_id: UUID, revoked_at: datetime) -> None: ...


TransactionFactory = Callable[[], IdentityTransaction]
