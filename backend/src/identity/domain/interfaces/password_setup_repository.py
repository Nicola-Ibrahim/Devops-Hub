"""One-time password setup persistence operations."""

from datetime import datetime
from typing import Protocol
from uuid import UUID


class PasswordSetupRepository(Protocol):
    async def issue_password_setup(
        self,
        *,
        user_id: UUID,
        digest: str,
        expires_at: datetime,
        actor_id: UUID,
        now: datetime,
    ) -> None: ...

    async def consume_password_setup(
        self, *, digest: str, password_hash: str, now: datetime
    ) -> bool: ...
