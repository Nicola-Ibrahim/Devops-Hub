"""Stored API token identity and lifecycle metadata; never the raw token."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ApiToken:
    id: UUID
    user_id: UUID
    project_id: UUID
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
