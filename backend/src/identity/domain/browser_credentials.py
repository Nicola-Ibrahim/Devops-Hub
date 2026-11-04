"""Pure rules for internal browser credentials and sessions."""

import re
from datetime import datetime, timedelta

from identity.domain.errors import IdentityValidationError

_USERNAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z")
_SESSION_IDLE = timedelta(minutes=30)
_SESSION_ABSOLUTE = timedelta(hours=8)


def normalize_user_name(value: str) -> str:
    normalized = value.strip().lower()
    if not _USERNAME.fullmatch(normalized):
        raise IdentityValidationError(
            "User name must use letters, numbers, dots, underscores or hyphens"
        )
    return normalized


def validate_password(value: str) -> None:
    if len(value) < 12 or len(value) > 1024:
        raise IdentityValidationError("Password must contain between 12 and 1024 characters")


def session_expiry(now: datetime) -> tuple[datetime, datetime]:
    return now + _SESSION_IDLE, now + _SESSION_ABSOLUTE


def session_is_valid(
    *,
    now: datetime,
    last_seen_at: datetime,
    idle_expires_at: datetime,
    absolute_expires_at: datetime,
    revoked_at: datetime | None,
    user_active: bool,
) -> bool:
    return (
        user_active
        and revoked_at is None
        and now < idle_expires_at
        and now < absolute_expires_at
        and now - last_seen_at < _SESSION_IDLE
    )
