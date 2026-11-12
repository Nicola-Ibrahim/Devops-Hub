"""Browser session entity without raw session or CSRF secrets."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from identity.domain.value_objects.session_expiry import SessionExpiry


@dataclass(frozen=True, slots=True)
class Session:
    id: UUID
    user_id: UUID
    created_at: datetime
    last_seen_at: datetime
    expiry: SessionExpiry
    revoked_at: datetime | None
    credential_version: int

    def accepts(self, *, now: datetime, user_active: bool, credential_version: int) -> bool:
        return (
            user_active
            and self.revoked_at is None
            and self.credential_version == credential_version
            and now < self.expiry.idle_at
            and now < self.expiry.absolute_at
            and now - self.last_seen_at < timedelta(minutes=30)
        )
