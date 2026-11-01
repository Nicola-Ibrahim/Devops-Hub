"""Pure snapshots exchanged between identity use cases and their storage port."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class IdentitySnapshot:
    user_id: UUID
    project_id: UUID
    user_active: bool


@dataclass(frozen=True)
class TokenSnapshot:
    token_id: UUID
    user_id: UUID
    project_id: UUID
    revoked_at: datetime | None


@dataclass(frozen=True)
class AuditRecord:
    actor_id: UUID | None
    project_id: UUID
    action: str
    outcome: str
    request_id: UUID
