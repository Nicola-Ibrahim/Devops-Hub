import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from dishka import Provider, Scope, provide
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from api.dependencies import ReadCurrentIdentity
from containers.factory import create_container
from containers.http import create_app
from identity.application.dto import IssueTokenCommand, PreparedApiToken
from identity.application.errors import IdentityUnavailable
from identity.application.ports import ApiTokenRepository
from identity.containers.operations import IssueApiTokenToFile
from identity.domain.credentials import ApiTokenAuthenticationDetails
from identity.domain.records import ApiTokenStatus, ProjectMembershipStatus
from identity.infra.credential_file import PrivateCredentialFile
from identity.infra.persistence.store import SQLAlchemyApiTokenRepository
from shared.infra.persistence.unit_of_work import DatabaseUnavailable, SqlAlchemyUnitOfWork
from shared.infra.settings import Settings

NOW = datetime(2026, 1, 1, tzinfo=UTC)
TOKEN = "synthetic-token-secret-that-is-never-logged"


class FakeSession:
    def __init__(
        self,
        *,
        fail_commit: BaseException | None = None,
        fail_rollback: BaseException | None = None,
        fail_close: BaseException | None = None,
    ) -> None:
        self.events: list[str] = []
        self.fail_commit = fail_commit
        self.fail_rollback = fail_rollback
        self.fail_close = fail_close

    async def begin(self) -> None:
        self.events.append("begin")

    async def commit(self) -> None:
        self.events.append("commit")
        if self.fail_commit:
            raise self.fail_commit

    async def rollback(self) -> None:
        self.events.append("rollback")
        if self.fail_rollback:
            raise self.fail_rollback

    async def close(self) -> None:
        self.events.append("close")
        if self.fail_close:
            raise self.fail_close


class FakeApiTokenRepository:
    def __init__(self, credential: ApiTokenAuthenticationDetails | None = None) -> None:
        self.credential = credential

    async def find_token_credential(self, digest: str) -> ApiTokenAuthenticationDetails | None:
        return self.credential

    async def ensure_developer_membership(
        self, *, user_name: str, project_name: str, new_role: str
    ) -> ProjectMembershipStatus:
        return ProjectMembershipStatus(uuid4(), uuid4(), True)

    async def insert_api_token(self, **kwargs) -> object:
        return uuid4()

    async def record_token_audit(self, event) -> None:
        return None

    async def find_api_token(self, token_id) -> ApiTokenStatus | None:
        return None

    async def revoke_api_token(self, token_id, revoked_at) -> None:
        return None


class FakeInnerIssue:
    def __init__(self, secret: str = TOKEN) -> None:
        self.secret = secret
        self.calls = 0

    async def execute(self, command: IssueTokenCommand) -> PreparedApiToken:
        self.calls += 1
        return PreparedApiToken(uuid4(), self.secret)


class FakeReceipt:
    def __init__(self, fail_cleanup: bool = False) -> None:
        self.removed = False
        self.fail_cleanup = fail_cleanup

    def remove_owned(self) -> None:
        self.removed = True
        if self.fail_cleanup:
            raise OSError("private path and secret must not leak")


class FakeDelivery:
    def __init__(self, *, fail_write: bool = False, receipt: FakeReceipt | None = None) -> None:
        self.fail_write = fail_write
        self.receipt = receipt or FakeReceipt()
        self.secrets: list[str] = []

    def write_new(self, secret: str) -> FakeReceipt:
        if self.fail_write:
            raise OSError("credential path details must not leak")
        self.secrets.append(secret)
        return self.receipt


class CapturedResponses:
    def __init__(self, app) -> None:
        self.app = app
        self.statuses: list[int] = []

    async def __call__(self, scope, receive, send) -> None:
        async def capture(message):
            if message["type"] == "http.response.start":
                self.statuses.append(message["status"])
            await send(message)

        await self.app(scope, receive, capture)


def settings() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://localhost:1/devops_hub_test",
        token_pepper="synthetic-unit-test-pepper-000000000000",
    )


def test_uow_commits_after_materialization_and_closes_before_return():
    session = FakeSession()
    unit = SqlAlchemyUnitOfWork(cast(AsyncSession, session))
    events = []

    async def action():
        events.append("action")
        return "domain-result"

    def materialize(value):
        events.append("materialize")
        return value.upper()

    assert asyncio.run(unit.run(action, materialize)) == "DOMAIN-RESULT"
    assert events == ["action", "materialize"]
    assert session.events == ["begin", "commit", "close"]
    assert unit.committed is True


@pytest.mark.parametrize("failure_point", ["action", "materialize", "commit"])
def test_uow_rolls_back_and_closes_on_operation_failures(failure_point):
    session = FakeSession(
        fail_commit=RuntimeError("commit failed") if failure_point == "commit" else None
    )
    unit = SqlAlchemyUnitOfWork(cast(AsyncSession, session))

    async def action():
        if failure_point == "action":
            raise ValueError("action failed")
        return "result"

    def materialize(value):
        if failure_point == "materialize":
            raise ValueError("response materialization failed")
        return value

    with pytest.raises(ValueError if failure_point != "commit" else RuntimeError):
        asyncio.run(unit.run(action, materialize))
    assert session.events[-2:] == ["rollback", "close"]
    assert unit.committed is False


def test_uow_translates_sqlalchemy_failure_and_records_rollback_close_failures():
    failure = SQLAlchemyError("database detail")
    session = FakeSession(
        fail_commit=failure,
        fail_rollback=RuntimeError("rollback detail"),
        fail_close=RuntimeError("close detail"),
    )
    unit = SqlAlchemyUnitOfWork(cast(AsyncSession, session))

    async def action():
        return "result"

    with pytest.raises(DatabaseUnavailable) as caught:
        asyncio.run(unit.run(action, lambda value: value))
    assert caught.value.__cause__ is failure
    assert caught.value.__notes__ == [
        "Database rollback failed; the original failure was preserved.",
        "Database session cleanup failed; the original failure was preserved.",
    ]
    assert not hasattr(failure, "__notes__")
    assert "database detail" not in str(caught.value)
    assert session.events == ["begin", "commit", "rollback", "close"]


def test_uow_preserves_primary_application_error_when_rollback_and_close_fail():
    session = FakeSession(
        fail_rollback=RuntimeError("rollback detail"),
        fail_close=RuntimeError("close detail"),
    )
    unit = SqlAlchemyUnitOfWork(cast(AsyncSession, session))

    async def action():
        raise ValueError("application failure")

    with pytest.raises(ValueError, match="application failure") as caught:
        asyncio.run(unit.run(action, lambda value: value))
    assert caught.value.__notes__ == [
        "Database rollback failed; the original failure was preserved.",
        "Database session cleanup failed; the original failure was preserved.",
    ]
    assert session.events == ["begin", "rollback", "close"]


def test_uow_rolls_back_and_closes_on_cancellation():
    session = FakeSession()
    unit = SqlAlchemyUnitOfWork(cast(AsyncSession, session))

    async def action():
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(unit.run(action, lambda value: value))
    assert session.events == ["begin", "rollback", "close"]
    assert unit.committed is False


def test_uow_does_not_rollback_or_reset_commit_when_close_fails_after_commit():
    session = FakeSession(fail_close=RuntimeError("close failed"))
    unit = SqlAlchemyUnitOfWork(cast(AsyncSession, session))

    async def action():
        return "committed result"

    with pytest.raises(RuntimeError, match="close failed"):
        asyncio.run(unit.run(action, lambda value: value))
    assert session.events == ["begin", "commit", "close"]
    assert unit.committed is True


def test_uow_is_single_use_after_success_and_rejects_concurrent_reuse():
    session = FakeSession()
    unit = SqlAlchemyUnitOfWork(cast(AsyncSession, session))
    first_path = Path("first")
    second_path = Path("second")
    calls: list[Path] = []

    async def action():
        calls.append(first_path)
        return "first result"

    asyncio.run(unit.run(action, lambda value: value))
    before = list(session.events)

    async def second_run():
        async def second_action():
            calls.append(second_path)
            return "second result"

        with pytest.raises(RuntimeError):
            await unit.run(second_action, lambda value: value)

    asyncio.run(second_run())
    assert calls == [first_path]
    assert session.events == before


def test_uow_rejects_concurrent_reuse_while_first_operation_is_active():
    session = FakeSession()
    unit = SqlAlchemyUnitOfWork(cast(AsyncSession, session))

    async def run_both():
        entered = asyncio.Event()
        release = asyncio.Event()
        calls = []

        async def first_action():
            calls.append("first")
            entered.set()
            await release.wait()
            return "first result"

        first = asyncio.create_task(unit.run(first_action, lambda value: value))
        await entered.wait()

        async def second_action():
            calls.append("second")
            return "second result"

        with pytest.raises(RuntimeError, match="one operation"):
            await unit.run(second_action, lambda value: value)
        assert calls == ["first"]
        assert session.events == ["begin"]
        release.set()
        assert await first == "first result"
        assert session.events == ["begin", "commit", "close"]

    asyncio.run(run_both())


def test_issue_to_file_rolls_back_write_failure_and_sql_commit_failure(tmp_path):
    command = IssueTokenCommand("developer", "demo")
    session = FakeSession()
    unit = SqlAlchemyUnitOfWork(cast(AsyncSession, session))
    inner = FakeInnerIssue()
    failing_delivery = FakeDelivery(fail_write=True)
    with pytest.raises(OSError):
        asyncio.run(IssueApiTokenToFile(inner, unit).execute(command, failing_delivery))
    assert session.events == ["begin", "rollback", "close"]
    assert failing_delivery.secrets == []

    session = FakeSession(fail_commit=SQLAlchemyError("database detail"))
    unit = SqlAlchemyUnitOfWork(cast(AsyncSession, session))
    inner = FakeInnerIssue()
    output = tmp_path / "sql-commit-failure"
    with pytest.raises(IdentityUnavailable) as caught:
        asyncio.run(
            IssueApiTokenToFile(inner, unit).execute(
                command,
                PrivateCredentialFile(output),
            )
        )
    assert not output.exists()
    assert caught.value.__cause__.__class__ is DatabaseUnavailable
    assert "database detail" not in str(caught.value)
    assert session.events == ["begin", "commit", "rollback", "close"]


def test_issue_to_file_preserves_replacement_and_cleanup_failure_note(tmp_path):
    command = IssueTokenCommand("developer", "demo")
    output = tmp_path / "replacement"
    delivery = PrivateCredentialFile(output)
    session = FakeSession(fail_commit=RuntimeError("commit failed"))
    unit = SqlAlchemyUnitOfWork(cast(AsyncSession, session))

    # Delivery receipt ownership is separately characterized by the identity tests;
    # the outer operation must leave a replacement in place during compensation.
    class ReplacingDelivery:
        def write_new(self, secret):
            receipt = delivery.write_new(secret)
            output.unlink()
            output.write_text("owned by another write")
            return receipt

    with pytest.raises(RuntimeError, match="commit failed"):
        asyncio.run(
            IssueApiTokenToFile(FakeInnerIssue(), unit).execute(command, ReplacingDelivery())
        )
    assert output.read_text() == "owned by another write"

    receipt = FakeReceipt(fail_cleanup=True)
    session = FakeSession(fail_commit=RuntimeError("primary commit failure"))
    unit = SqlAlchemyUnitOfWork(cast(AsyncSession, session))
    with pytest.raises(RuntimeError, match="primary commit failure") as caught:
        asyncio.run(
            IssueApiTokenToFile(FakeInnerIssue(), unit).execute(
                command, FakeDelivery(receipt=receipt)
            )
        )
    assert receipt.removed
    assert caught.value.__notes__ == [
        "Credential cleanup failed; the original failure was preserved."
    ]
    assert "private path" not in " ".join(caught.value.__notes__)


def test_issue_to_file_keeps_credential_after_commit_then_close_failure(tmp_path):
    output = tmp_path / "committed-credential"
    session = FakeSession(fail_close=RuntimeError("close failed after commit"))
    unit = SqlAlchemyUnitOfWork(cast(AsyncSession, session))

    with pytest.raises(RuntimeError, match="close failed after commit"):
        asyncio.run(
            IssueApiTokenToFile(FakeInnerIssue(), unit).execute(
                IssueTokenCommand("developer", "demo"),
                PrivateCredentialFile(output),
            )
        )
    assert output.read_text() == TOKEN + "\n"
    assert output.stat().st_mode & 0o777 == 0o600
    assert unit.committed is True


@pytest.mark.parametrize("scope_kind", ["same", "concurrent"])
def test_container_scopes_bind_fresh_sessions_and_ready_identity_query(scope_kind):
    engine = create_async_engine(
        "postgresql+psycopg://localhost:1/devops_hub_test", poolclass=NullPool
    )
    sessions: list[FakeSession] = []

    class SessionOverride(Provider):
        @provide(scope=Scope.REQUEST, provides=AsyncSession, override=True)
        def session(self) -> AsyncSession:
            result = FakeSession()
            sessions.append(result)
            return cast(AsyncSession, result)

    container = create_container(settings(), engine=engine, overrides=(SessionOverride(),))

    async def resolve_request():
        async with container() as scope:
            query = await scope.get(ReadCurrentIdentity)
            unit = await scope.get(SqlAlchemyUnitOfWork)
            repository = await scope.get(ApiTokenRepository)
            assert callable(query.execute)
            assert isinstance(repository, SQLAlchemyApiTokenRepository)
            assert repository._session is unit.session
            await unit.session.close()
            return unit.session

    async def run():
        if scope_kind == "same":
            first = await resolve_request()
            second = await resolve_request()
            assert first is not second
        else:
            first, second = await asyncio.gather(resolve_request(), resolve_request())
            assert first is not second
        await container.close()
        await engine.dispose()

    asyncio.run(run())
    assert len(sessions) == (2 if scope_kind == "same" else 2)
    assert all(session.events == ["close"] for session in sessions)


def test_http_commit_failure_returns_503_without_success_response_start():
    now = datetime.now(UTC)
    repository = FakeApiTokenRepository(
        ApiTokenAuthenticationDetails(
            uuid4(),
            uuid4(),
            uuid4(),
            "developer",
            ("catalog:read",),
            True,
            now + timedelta(hours=1),
            None,
        )
    )
    session = FakeSession(fail_commit=SQLAlchemyError("database detail"))

    class Overrides(Provider):
        @provide(scope=Scope.REQUEST, provides=AsyncSession, override=True)
        def session(self) -> AsyncSession:
            return cast(AsyncSession, session)

        @provide(scope=Scope.REQUEST, provides=ApiTokenRepository, override=True)
        def repository(self) -> ApiTokenRepository:
            return repository

    engine: AsyncEngine = create_async_engine(
        "postgresql+psycopg://localhost:1/devops_hub_test", poolclass=NullPool
    )
    container = create_container(settings(), engine=engine, overrides=(Overrides(),))
    capture = CapturedResponses(create_app(container=container))
    try:
        with TestClient(capture) as client:
            response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {TOKEN}"})
        assert response.status_code == 503
        assert capture.statuses == [503]
        assert "database detail" not in response.text
        assert session.events == ["begin", "commit", "rollback", "close"]
    finally:
        asyncio.run(container.close())
        asyncio.run(engine.dispose())


@pytest.mark.parametrize("ownership", ["host", "caller_engine", "caller_container"])
def test_http_lifespan_disposes_only_host_owned_database(monkeypatch, ownership):
    from httpx import ASGITransport, AsyncClient

    disposed = []
    original = AsyncEngine.dispose

    async def observe(engine, *args, **kwargs):
        disposed.append(engine)
        await original(engine, *args, **kwargs)

    monkeypatch.setattr(AsyncEngine, "dispose", observe)

    async def exercise():
        engine = create_async_engine(settings().database_url.get_secret_value(), poolclass=NullPool)
        container = None
        if ownership == "caller_container":
            container = create_container(settings())
            app = create_app(container=container)
        elif ownership == "caller_engine":
            app = create_app(settings(), engine=engine)
        else:
            app = create_app(settings())
        # Keep caller/app cleanup on the same event loop; TestClient loop shutdown
        # finalizes async generators and cannot model a still-running caller owner.
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
                assert (await client.get("/api/v1/me")).status_code == 401
        if ownership == "host":
            assert len(disposed) == 1 and disposed[0] is not engine
        else:
            assert disposed == []
        if container is not None:
            await container.close()
            assert len(disposed) == 1 and disposed[0] is not engine
        await engine.dispose()
        assert disposed[-1] is engine

    asyncio.run(exercise())
