"""Idle and absolute browser-session expiry values."""

from dataclasses import dataclass
from datetime import datetime, timedelta

_IDLE = timedelta(minutes=30)
_ABSOLUTE = timedelta(hours=8)


@dataclass(frozen=True, slots=True)
class SessionExpiry:
    idle_at: datetime
    absolute_at: datetime

    @classmethod
    def from_login(cls, now: datetime) -> "SessionExpiry":
        return cls(now + _IDLE, now + _ABSOLUTE)
