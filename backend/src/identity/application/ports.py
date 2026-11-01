from datetime import datetime
from typing import Protocol
from uuid import UUID

from identity.domain.credentials import ApiTokenAuthenticationDetails
from identity.domain.records import ApiTokenAuditEvent, ApiTokenStatus, ProjectMembershipStatus


class TokenHasher(Protocol):
    def digest(self, token: str) -> str: ...


class TokenGenerator(Protocol):
    def generate(self) -> str: ...


class CredentialReceipt(Protocol):
    def remove_owned(self) -> None: ...


class CredentialDelivery(Protocol):
    def write_new(self, secret: str) -> CredentialReceipt: ...


class ApiTokenRepository(Protocol):
    """Identity-owned token queries/writes; transaction completion is external."""

    async def find_token_credential(self, digest: str) -> ApiTokenAuthenticationDetails | None: ...

    async def ensure_developer_membership(
        self, *, user_name: str, project_name: str, new_role: str
    ) -> ProjectMembershipStatus: ...

    async def insert_api_token(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        digest: str,
        scopes: tuple[str, ...],
        expires_at: datetime,
        created_at: datetime,
    ) -> UUID: ...

    async def record_token_audit(self, event: ApiTokenAuditEvent) -> None: ...

    async def find_api_token(self, token_id: UUID) -> ApiTokenStatus | None: ...

    async def revoke_api_token(self, token_id: UUID, revoked_at: datetime) -> None: ...
