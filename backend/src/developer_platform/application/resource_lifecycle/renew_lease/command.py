from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class RenewDatabaseLease:
    resource_id: UUID
    expected_revision: int
    expires_at: datetime
