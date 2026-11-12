"""Identity message registration and lazy handler resolution."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from identity.application.authenticate_api_token.query import AuthenticateApiTokenQuery
from identity.application.authenticate_session.query import AuthenticateSessionQuery
from identity.application.change_password.command import ChangePasswordCommand
from identity.application.list_project_members.query import ListProjectMembersQuery
from identity.application.list_sessions.query import ListSessionsQuery
from identity.application.login.command import LoginCommand
from identity.application.logout.command import LogoutCommand
from identity.application.logout_all_sessions.command import LogoutAllSessionsCommand
from identity.application.manage_project_membership.command import ManageProjectMembershipCommand
from identity.application.revoke_session.command import RevokeSessionCommand
from identity.application.rotate_csrf.command import RotateCsrfCommand
from identity.application.select_active_project.command import SelectActiveProjectCommand
from identity.domain.credentials import ApiTokenAuthenticationDetails
from identity.infra.composition.module import (
    IDENTITY_HANDLER_REGISTRY,
    IdentityModuleDispatcher,
)
from identity.infra.hosts.api_token_authentication import TokenAuthenticationHost
from identity.infra.hosts.module_handlers import LoginHandler
from shared.dispatch import HandlerRegistry, RegistrationError, UnsupportedMessage
from shared.infra.persistence.unit_of_work import SqlAlchemyUnitOfWork


def test_identity_messages_have_explicit_complete_registrations() -> None:
    assert IDENTITY_HANDLER_REGISTRY.commands[LoginCommand] is LoginHandler
    assert set(IDENTITY_HANDLER_REGISTRY.commands) == {
        LoginCommand,
        RotateCsrfCommand,
        SelectActiveProjectCommand,
        LogoutCommand,
        LogoutAllSessionsCommand,
        RevokeSessionCommand,
        ChangePasswordCommand,
        ManageProjectMembershipCommand,
    }
    assert set(IDENTITY_HANDLER_REGISTRY.queries) == {
        AuthenticateApiTokenQuery,
        AuthenticateSessionQuery,
        ListSessionsQuery,
        ListProjectMembersQuery,
    }


def test_identity_registry_rejects_incomplete_or_ambiguous_bindings() -> None:
    with pytest.raises(RegistrationError, match="more than one"):
        HandlerRegistry(
            commands=[(LoginCommand, LoginHandler)] * 2,
            queries=[],
        )
    with pytest.raises(RegistrationError, match="required command"):
        HandlerRegistry(
            commands=[],
            queries=[],
            required_commands=[LoginCommand],
        )


def test_identity_dispatch_resolves_only_selected_handler() -> None:
    resolved: list[type[object]] = []

    class SelectedHandler:
        async def execute(self, command: LoginCommand) -> str:
            return command.user_name

    instances = {LoginHandler: SelectedHandler()}

    class Container:
        async def get(self, handler: type[object]) -> object:
            resolved.append(handler)
            return instances[handler]

    class UnknownQuery:
        pass

    async def run() -> None:
        dispatcher = IdentityModuleDispatcher(Container())
        command = LoginCommand("alice", "secret", None, None)
        assert await dispatcher.execute(command) == "alice"
        assert resolved == [LoginHandler]
        with pytest.raises(UnsupportedMessage, match="Unsupported query"):
            await dispatcher.query(UnknownQuery())
        assert resolved == [LoginHandler]

    asyncio.run(run())


def test_bearer_query_uses_its_own_transaction_and_leaves_platform_unit_unused(monkeypatch) -> None:
    now = datetime.now(UTC)
    events: list[str] = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def begin(self):
            events.append("begin")

        async def commit(self):
            events.append("commit")

        async def rollback(self):
            events.append("rollback")

        async def close(self):
            events.append("close")

    class Repository:
        def __init__(self, session):
            assert isinstance(session, Session)

        async def find_token_credential(self, digest):
            assert digest == "digest"
            return ApiTokenAuthenticationDetails(
                uuid4(),
                uuid4(),
                uuid4(),
                "developer",
                ("resources:read",),
                True,
                now + timedelta(hours=1),
                None,
            )

    class Hasher:
        def digest(self, token):
            return "digest"

    monkeypatch.setattr(
        "identity.infra.hosts.api_token_authentication.SQLAlchemyApiTokenRepository", Repository
    )
    platform_unit = SqlAlchemyUnitOfWork(Session())
    host = TokenAuthenticationHost(lambda: Session(), Hasher(), lambda: now)

    async def run() -> None:
        principal = await host.authenticate("t" * 43)
        assert principal.role == "developer"

    asyncio.run(run())
    assert events == ["begin", "commit", "close"]
    assert platform_unit._used is False
