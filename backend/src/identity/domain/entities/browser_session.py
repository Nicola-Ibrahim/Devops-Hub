"""Browser session entity without raw session or CSRF secrets."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from identity.domain.value_objects.session_expiry import SessionExpiry


@dataclass(frozen=True, slots=True)
class BrowserSession:
    id: UUID
    user_id: UUID
    created_at: datetime
    last_seen_at: datetime
    expiry: SessionExpiry
    revoked_at: datetime | None
