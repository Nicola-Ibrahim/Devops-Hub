"""Temporary resource lease value."""

from dataclasses import dataclass
from datetime import datetime

from developer_platform.domain.errors import LeaseViolation


@dataclass(frozen=True, slots=True)
class ResourceLease:
    created_at: datetime
    expires_at: datetime
    max_lifetime_seconds: int

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise LeaseViolation("Lease times must be timezone-aware.")
        if self.max_lifetime_seconds <= 0 or self.expires_at <= self.created_at:
            raise LeaseViolation("Resource lease is invalid.")
