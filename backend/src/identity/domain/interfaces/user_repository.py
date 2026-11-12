"""Identity account persistence operations used by account use cases."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from identity.domain.records import AccountCredentials, SessionPrincipal


class UserRepository(Protocol):
    async def find_login_account(self, user_name: str) -> AccountCredentials | None: ...

    async def complete_login(
        self,
        *,
        user_name: str,
        username_digest: str,
        expected_version: int | None,
        accepted: bool,
        token_digest: str,
        csrf_digest: str,
        now: datetime,
    ) -> tuple[SessionPrincipal, UUID, datetime] | None: ...

    async def change_password(
        self, *, user_id: UUID, expected_version: int, password_hash: str, now: datetime
    ) -> bool: ...

    async def create_user(
        self, user_name: str, password_hash: str, actor_id: UUID | None, now: datetime
    ) -> UUID: ...

    async def set_user_active(
        self, *, actor_id: UUID, user_id: UUID, active: bool, now: datetime
    ) -> None: ...

    async def bootstrap_first_project_admin(
        self, *, user_id: UUID, project_id: UUID, now: datetime
    ) -> None: ...
