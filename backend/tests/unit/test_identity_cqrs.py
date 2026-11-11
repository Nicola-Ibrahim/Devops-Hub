import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from identity.application.browser_sessions.command import RefreshBrowserSessionCommand
from identity.application.browser_sessions.handler import RefreshBrowserSessionHandler
from identity.application.internal_users.command import CreateInternalUserCommand
from identity.application.internal_users.handler import CreateInternalUserHandler
from identity.application.project_memberships.command import SetProjectMembershipCommand
from identity.application.project_memberships.handler import (
    ListProjectMembersHandler,
    SetProjectMembershipHandler,
)
from identity.application.project_memberships.query import ListProjectMembersByActorQuery
from identity.domain.browser_identity import BrowserPrincipal
from identity.domain.errors import IdentityValidationError

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class Passwords:
    def hash(self, password: str) -> str:
        return f"encoded:{password}"

    def verify(self, password: str, encoded: str) -> bool:
        return encoded == f"encoded:{password}"


def test_create_internal_user_handler_builds_normalized_domain_name() -> None:
    class Repository:
        async def create_user(self, user_name, password_hash, actor_id, now):
            self.values = (user_name, password_hash, actor_id, now)
            return uuid4()

    repository = Repository()
    asyncio.run(
        CreateInternalUserHandler(repository, Passwords(), lambda: NOW).execute(
            CreateInternalUserCommand(" Developer ", "long-enough-password")
        )
    )

    assert repository.values[:2] == ("developer", "encoded:long-enough-password")


def test_membership_command_validates_project_role_before_persistence() -> None:
    class Repository:
        async def set_membership(self, **values):
            raise AssertionError(f"unexpected persistence call: {values}")

    with pytest.raises(IdentityValidationError, match="role"):
        asyncio.run(
            SetProjectMembershipHandler(Repository(), lambda: NOW).execute(
                SetProjectMembershipCommand(uuid4(), uuid4(), uuid4(), "owner")
            )
        )


def test_project_member_query_is_read_only_and_receives_authorized_actor() -> None:
    actor_id, project_id = uuid4(), uuid4()

    class ReadRepository:
        async def list_project_members(self, *, actor_id, project_id):
            self.values = (actor_id, project_id)
            return ()

    repository = ReadRepository()
    result = asyncio.run(
        ListProjectMembersHandler(repository).execute(
            ListProjectMembersByActorQuery(actor_id, project_id)
        )
    )

    assert result == ()
    assert repository.values == (actor_id, project_id)


def test_session_refresh_is_explicitly_a_command() -> None:
    user_id, session_id = uuid4(), uuid4()
    principal = BrowserPrincipal(user_id, "dev", session_id, None, None, None, (), (), "")

    class Repository:
        async def authenticate_session(self, **values):
            self.values = values
            return principal, "encoded-token"

    repository = Repository()
    result = asyncio.run(
        RefreshBrowserSessionHandler(
            repository, lambda: NOW, lambda value: f"digest:{value}"
        ).execute(RefreshBrowserSessionCommand("private-session"))
    )

    assert result == principal
    assert repository.values == {
        "token_digest": "digest:private-session",
        "project_id": None,
        "now": NOW,
    }
    assert "private-session" not in repr(RefreshBrowserSessionCommand("private-session"))
